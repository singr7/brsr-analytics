# Terraform estate

Single-node production estate for BRSR Lens, implementing the topology in
[`DEPLOYMENT.md`](../../DEPLOYMENT.md) section 1.

The full turn-up procedure is
[`docs/operations/PRODUCTION_DEPLOYMENT.md`](../../docs/operations/PRODUCTION_DEPLOYMENT.md).
This file covers the Terraform layer only.

## What it creates

| Area | Resources |
|---|---|
| Network | VPC, one public subnet, internet gateway, route table, S3 gateway endpoint |
| Security | App SG (80/443 in, no SSH), batch SG (egress only, reaches PG/Redis by SG reference) |
| Compute | App EC2 (t3.large, IMDSv2 required, encrypted root), separate encrypted data volume with `prevent_destroy`, Elastic IP, optional batch node behind a flag |
| Storage | `filings-raw`, `artifacts`, `backups` — versioned, AES256, public-access-blocked, insecure-transport denied, lifecycle rules |
| Registry | ECR repositories `brsrlens/api` and `brsrlens/web` with scan-on-push and retention |
| Config | SSM parameters under `/brsrlens/<env>/env/`, plus release pointers |
| Identity | Node instance profile (S3, SSM read, ECR pull, SES, SNS publish) and a CI deployer role |
| Observability | SNS topic, status/CPU/disk/memory alarms, dead-man backup alarm, log group, monthly budget |
| DNS | Optional Route 53 A record |

## Usage

```sh
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # fill in domain, alert email, zone id
cp backend.tf.example backend.tf               # fill in the state bucket
terraform init
terraform plan
terraform apply
terraform output next_steps
```

`terraform.tfvars` and `backend.tf` are gitignored. The example files are the
committed templates.

## Design decisions worth knowing before you change something

**The data volume is separate and protected.** Postgres, the object store and
raw filings live on `aws_ebs_volume.data`, which carries `prevent_destroy`. The
node can be rebuilt without losing a corpus that took a supervised cohort run to
produce. `terraform destroy` will refuse until that lifecycle block is removed
deliberately.

**The AMI is pinned by `ignore_changes`.** `data.aws_ssm_parameter.al2023`
resolves to a newer image every few weeks. Without the ignore, an unrelated
`apply` would replace the running node. OS security patches are applied in place
by `dnf-automatic`; a rebuild is a deliberate operator action.

**Buckets use AES256, not KMS.** `api/app/services/storage.py` signs its own
SigV4 requests with `x-amz-server-side-encryption: AES256`. Switching the bucket
to KMS without changing that header makes every upload fail the bucket policy.

**No SSH ingress and no key pair.** Access is SSM Session Manager. The
`break_glass_ssh_cidrs` variable exists for an incident and should be empty
again afterwards.

**Terraform does not own secrets.** Operator parameters are created once with a
`CHANGE_ME` placeholder and `ignore_changes = [value]`. Real values are written
with `aws ssm put-parameter --overwrite` and never appear in state, in a plan, or
in a pull request. `render-env.sh` refuses to start the stack while any
parameter still reads `CHANGE_ME`.

**`DATABASE_URL` is not a parameter.** It is built on the node from
`POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB`, so the connection string
cannot drift from the password Postgres was initialised with.

**Acquisition ships closed.** `SOURCE_NSE_BRSR_ENABLED` is created as `"false"`.
Flipping it in Parameter Store is the technical expression of the legal-gate
signature in `docs/gates/legal.md`, and `ingest.sh` refuses to fetch while it is
off.

## Sandbox rehearsal

Infrastructure changes rehearse in a sandbox before production, per
`DEPLOYMENT.md` section 3. Use a separate AWS account with `environment =
"sandbox"` and a distinct state key. The `environment` value is part of every
resource name, the SSM prefix and the bucket suffix, so the two estates cannot
collide even in one account — though a separate account remains the intent, so a
sandbox mistake cannot reach production data.

Use capped LLM provider keys in sandbox. A runaway reprocess loop must not be
able to spend the production budget.

## Wiring CI

`aws_iam_role.deployer` is created with a placeholder trust policy that allows
the account root. Before wiring GitHub Actions, replace its
`assume_role_policy` with a GitHub OIDC trust statement scoped to this
repository and branch, so CI needs no long-lived AWS keys:

```hcl
principals {
  type        = "Federated"
  identifiers = ["arn:aws:iam::<account>:oidc-provider/token.actions.githubusercontent.com"]
}
condition {
  test     = "StringLike"
  variable = "token.actions.githubusercontent.com:sub"
  values   = ["repo:<org>/<repo>:ref:refs/heads/main"]
}
```

The role can push images and start a deployment. It cannot read application
data, which is the point of separating it from the node role.

## Verification status

`terraform fmt -check` and `terraform validate` pass against AWS provider
5.100.0. A `plan` has not been run — that requires credentials for the target
account and is the first step of the turn-up procedure.
