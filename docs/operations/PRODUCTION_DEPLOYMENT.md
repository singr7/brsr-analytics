# Production deployment — AWS turn-up runbook

Takes an empty AWS account to a live, TLS-terminated BRSR Lens serving the FY25
NIFTY 100 corpus, with a CLI for ingesting the next batch of filings.

Read alongside [`DEPLOYMENT.md`](../../DEPLOYMENT.md) (topology and doctrine) and
[`NSE_BRSR_INGESTION.md`](NSE_BRSR_INGESTION.md) (what the acquisition CLI does).

**Estimated time:** 90 minutes to a live site, plus 30–60 minutes for the corpus
depending on which bootstrap path you take in step 8.

---

## What gets built

```
                            Route 53  ──────►  Elastic IP
                                                   │
  ┌────────────────────────────────────────────────▼──────────────────────────┐
  │  EC2 app node (t3.large, Amazon Linux 2023, no SSH, SSM only)             │
  │                                                                           │
  │   web (nginx)  ── TLS, HSTS, rate limits, static bundle, /api proxy       │
  │        │                                                                  │
  │   api (FastAPI ×2)   worker (Celery)   scheduler (Beat)                   │
  │        │                    │                │                            │
  │   postgres 16 + pgvector          redis 7                                 │
  │        └──────────── /opt/brsrlens/data (separate encrypted EBS volume) ──┤
  └───────────────────────────────────────────────────────────────────────────┘
        │                        │                          │
     ECR images          S3: filings-raw,            SSM Parameter Store
                         artifacts, backups           (config + secrets)
```

Everything the operator does runs through `ops/bin/brsrlens-prod`, which drives
the node over SSM. There is no SSH ingress in normal operation and no key pair.

---

## Prerequisites

On your workstation:

- AWS CLI v2, authenticated against the target account with administrator rights
  for the first apply
- Terraform ≥ 1.6
- Docker with buildx (images are built for `linux/amd64`)
- `jq`
- A registered domain you can create DNS records for

Decisions to make before you start:

| Decision | Default | Notes |
|---|---|---|
| Region | `ap-south-1` | Mumbai keeps Indian regulatory filings in-country |
| Domain | — | Certbot issues for exactly this name |
| DNS in Route 53 | yes | Set `create_dns_record = false` to manage it elsewhere |
| LLM provider | — | `LLM_PROVIDER=fake` is **rejected** in production by settings validation |

---

## 1. Bootstrap the Terraform state backend

State must be remote and locked before anything else exists, because more than
one person will run this.

```sh
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
REGION=ap-south-1

aws s3api create-bucket \
  --bucket "brsrlens-tfstate-${ACCOUNT}" \
  --region "$REGION" \
  --create-bucket-configuration LocationConstraint="$REGION"

aws s3api put-bucket-versioning \
  --bucket "brsrlens-tfstate-${ACCOUNT}" \
  --versioning-configuration Status=Enabled

aws s3api put-public-access-block \
  --bucket "brsrlens-tfstate-${ACCOUNT}" \
  --public-access-block-configuration \
      BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws dynamodb create-table \
  --table-name brsrlens-tfstate-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "$REGION"
```

---

## 2. Apply the estate

```sh
cd infra/terraform
cp backend.tf.example backend.tf              # fill in the bucket from step 1
cp terraform.tfvars.example terraform.tfvars  # domain, alert email, zone id

terraform init
terraform plan     # read it; nothing here should surprise you
terraform apply
```

Then capture the outputs you will need throughout:

```sh
export AWS_REGION=ap-south-1
export BRSRLENS_INSTANCE_ID=$(terraform output -raw app_instance_id)
terraform output next_steps
```

> **Confirm the SNS subscription email now.** AWS sends a confirmation to
> `alert_email`. Until it is accepted, the subscription stays
> `PendingConfirmation` and **no alarm reaches anyone** — including the dead-man
> backup alarm.

---

## 3. Set the operator secrets

Terraform created these parameters with a `CHANGE_ME` placeholder and does not
own their values. `render-env.sh` refuses to start the stack while any of them
is still unset, so a half-configured deploy fails early and legibly.

List what is outstanding:

```sh
terraform output -raw unset_parameters_command | sh
```

Set each one. Generate the two credentials rather than choosing them:

```sh
PREFIX=/brsrlens/prod/env
put() { aws ssm put-parameter --name "$PREFIX/$1" --type SecureString --overwrite --value "$2" >/dev/null && echo "set $1"; }

put JWT_SECRET        "$(openssl rand -base64 48 | tr -d '\n=')"
put POSTGRES_PASSWORD "$(openssl rand -base64 32 | tr -d '\n=/+')"

put EMAIL_FROM        "hello@yourdomain.com"
put SMTP_USER         "<SES SMTP username>"
put SMTP_PASSWORD     "<SES SMTP password>"

# LLM_PROVIDER must not be 'fake': settings validation rejects it in production
# so fixture responses can never be served as if extracted from a real filing.
put LLM_PROVIDER      "openai"
put LLM_API_KEY       "sk-..."
put LLM_BASE_URL      "https://api.openai.com/v1"
put LLM_MODEL         "gpt-4.1-mini"

# A monitored address. It goes in the User-Agent of every request to NSE, and
# is what the exchange contacts if they want the crawl stopped.
put NSE_BRSR_CONTACT  "compliance@yourdomain.com"

put LEAD_RECIPIENT_EMAIL        "bd@yourdomain.com"
put LEAD_WEBHOOK_URL            ""
put LEAD_WEBHOOK_SECRET         ""
put ANALYTICS_DIGEST_RECIPIENTS "team@yourdomain.com"
put BILLING_OPS_EMAIL           "ops@yourdomain.com"
```

Optionally restrict the admin cockpit at the network layer as well as by role:

```sh
aws ssm put-parameter --name "$PREFIX/ADMIN_ALLOW_CIDRS" --type String \
  --value "203.0.113.10/32,198.51.100.0/24" --overwrite
```

`POSTGRES_PASSWORD` is written **once**, before the first deploy. Postgres
initialises its data directory with whatever password is set at first start;
changing the parameter later does not change the database's own password. To
rotate it, change it in Postgres first, then update the parameter.

`DATABASE_URL` is deliberately absent — the node builds it from the user,
password and database name, so the two can never drift apart.

### SES

New SES accounts are sandboxed and can only send to verified addresses. Verify
your domain, create SMTP credentials, and request production access before
launch, or signup verification emails will not be delivered.

---

## 4. Publish the operator scripts and build the images

The node pulls its operator scripts from the artifacts bucket rather than having
them baked into the AMI, so fixing `deploy.sh` never requires rebuilding a node.

```sh
cd ../..                       # repository root
ops/bin/brsrlens-prod push-ops
ops/bin/brsrlens-prod build    # tags as sha-<short commit>
```

`build` produces two images:

- `brsrlens/api` — FastAPI, Celery worker and Beat scheduler in one image,
  multi-stage, running as a non-root user
- `brsrlens/web` — nginx with the built and prerendered frontend bundle

The frontend's API base URL is baked in at build time from the `FRONTEND_URL`
parameter, so the image is specific to the environment it was built for.

---

## 5. First deploy

```sh
ops/bin/brsrlens-prod deploy sha-abc1234
```

`deploy.sh` runs in a deliberate order:

1. pulls both images **before** touching anything running, so a bad tag fails
   while the current release is still serving;
2. renders `.env` from Parameter Store;
3. starts Postgres and Redis and waits for readiness;
4. applies migrations expand-only, with the old code still up — a failed
   migration leaves a working site rather than a half-migrated one;
5. restarts the app services and waits for health;
6. runs the smoke suite;
7. **rolls back automatically** to the previous tag if health or smoke fails.

The corpus assertion in the smoke suite will fail on this first deploy — the
database is empty until step 8. That is expected and it is why step 8 exists.

---

## 6. DNS and TLS

If `create_dns_record = true`, Terraform already created the A record. Otherwise
point your record at `terraform output -raw elastic_ip`.

Wait for DNS to resolve publicly — Let's Encrypt fetches the challenge over the
internet, not from localhost:

```sh
dig +short brsrlens.example.com
```

Rehearse against staging first (no rate limit), then issue for real:

```sh
ops/bin/brsrlens-prod cert staging
ops/bin/brsrlens-prod cert issue
```

Until this runs, the site serves a self-signed placeholder that the web
container generates on first boot. That placeholder is what lets nginx start at
all before a certificate exists.

Verify from outside:

```sh
curl -sI https://brsrlens.example.com | head -1
curl -sI https://brsrlens.example.com | grep -i strict-transport
curl -sI http://brsrlens.example.com  | head -1   # expect 301
```

Renewal runs weekly from cron and reloads nginx without downtime.

---

## 7. Create the platform admin account

```sh
ops/bin/brsrlens-prod shell
```

On the node:

```sh
cd /opt/brsrlens
source env/node.env
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec api python -m api.app.db.seed
```

`seed` creates access fixtures and taxonomy definitions **only**. It creates no
company or filing data — nothing in this product should ever show a made-up
company.

Sign up through the site, then promote yourself:

```sh
ops/bin/brsrlens-prod run 'source /opt/brsrlens/env/node.env
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres \
  psql -U brsrlens -d brsrlens -c "update users set is_admin = true where email = '"'"'you@yourdomain.com'"'"'"'
```

Because `AUTH_EXPOSE_VERIFICATION_TOKEN` is forced to `false` in production, the
verification email must actually arrive — which is why SES must work before this
step.

---

## 8. Build the corpus — 100 filings

Two paths. **Read both before choosing.**

### Path A — ingest from NSE on the node (reproducible, preferred)

This is the designed path: the corpus is rebuilt from official sources, and
every artifact is checksummed and stored as it arrives.

First, open the legal gate. Acquisition ships fail-closed and `ingest.sh`
refuses to fetch while it is shut:

```sh
# Only after docs/gates/legal.md is signed and NSE_BRSR_CONTACT is monitored.
aws ssm put-parameter --name /brsrlens/prod/env/SOURCE_NSE_BRSR_ENABLED \
  --type String --overwrite --value true
ops/bin/brsrlens-prod run 'systemctl restart brsrlens'
```

Canary one company before committing to a cohort:

```sh
ops/bin/brsrlens-prod ingest initial --start 0 --limit 1
ops/bin/brsrlens-prod ingest status
```

If that returns one parsed filing with non-zero facts, run the cohort. It is
rate-limited to one request every two seconds by design, so a hundred companies
takes roughly 25–40 minutes:

```sh
ops/bin/brsrlens-prod ingest initial --limit 25
ops/bin/brsrlens-prod ingest next --limit 25
ops/bin/brsrlens-prod ingest next --limit 25
ops/bin/brsrlens-prod ingest next --limit 25
```

> **The known risk with this path.** NSE serves both the registry CSVs and the
> filing index from a public web front end that is unfriendly to datacenter IP
> ranges. The ingest worked from a residential connection; it has **not** been
> proven from an EC2 address. If the canary returns zero discovered filings or
> HTTP 403, that is what happened — the code is fine, the source is refusing the
> address. Use Path B, and treat routing the crawl through an egress that NSE
> accepts as a follow-up task rather than a blocker for launch.

### Path B — transfer the corpus you already have

Reproduces the exact database you have locally, including the 204,880 raw facts,
1,255 pins and 351 scores. Use this when Path A is blocked, or to get a live
site today and settle the crawl path afterwards.

On your workstation, from a healthy local stack:

```sh
docker compose exec -T postgres pg_dump -U brsrlens -d brsrlens \
  --clean --if-exists --no-owner --no-privileges | gzip -9 > corpus-fy25.sql.gz

BUCKET=$(cd infra/terraform && terraform output -json buckets | jq -r .backups)
aws s3 cp corpus-fy25.sql.gz "s3://${BUCKET}/postgres/prod-imported-fy25.sql.gz" --sse AES256
```

On the node:

```sh
ops/bin/brsrlens-prod shell
sudo /opt/brsrlens/bin/restore.sh prod-imported-fy25.sql.gz
```

`restore.sh` snapshots the current database first, requires you to type the
environment name, and asserts afterwards that every metric still resolves to a
pinned field version — a restore that broke lineage is rejected rather than
served.

Raw filing artifacts live in object storage, not in the dump. Copy them too, so
lineage links resolve to a stored document rather than only to the NSE URL:

```sh
FILINGS=$(cd infra/terraform && terraform output -json buckets | jq -r .filings)
aws s3 sync .data/object-store/filings-raw/ "s3://${FILINGS}/" --sse AES256
```

### Either path — verify

```sh
ops/bin/brsrlens-prod ingest status
ops/bin/brsrlens-prod smoke
```

Expect roughly: 100 companies, 93 parsed filings, 7 missing, 204,880 raw XBRL
facts, 1,255 pins, 1,527 metrics, 351 scores. The smoke suite's corpus assertion
should now pass.

---

## 9. Ingesting the next batch, from then on

This is the routine you asked for and the one you will use most.

```sh
# What is in the corpus now, and the last ten runs
ops/bin/brsrlens-prod ingest status

# Next batch. Advances the persisted registry cursor, so repeated calls walk
# forward through the cohort rather than re-fetching the same companies.
ops/bin/brsrlens-prod ingest next --limit 10

# Re-check companies already ingested. Does NOT advance the cursor, and replaces
# an artifact only when the official XBRL checksum changed.
ops/bin/brsrlens-prod ingest refresh --limit 25

# A new financial year
ops/bin/brsrlens-prod ingest next --fy 2026 --limit 25

# Re-map and rebuild after a mapping review, without re-fetching anything
ops/bin/brsrlens-prod ingest publish --fy 2025
```

**Each run is complete on its own.** `ingest.sh` takes a database snapshot
first, holds a lock so two runs cannot advance the cursor concurrently, and
always chains `--publish` — which maps the new facts, pins them, rebuilds
metrics and scores, and invalidates the semantic cache. It then prints the
corpus counts before and after and re-runs the smoke suite. Nothing else is
needed for the new filings to appear across Explore, Ask, sector scorecards,
company views, benchmarks and the export API.

### Reading the output

```
run=... status=completed discovered=10 fetched=10 parsed=10 missing=0 errors=0
published=54 pinned=118 mapping_missing=40 withheld=2 metrics=1631 scores=375
```

| Field | Meaning | Action |
|---|---|---|
| `missing` | No filing published at the portal for that symbol and year | Confirm before ever reporting it as non-compliance |
| `mapping_missing` | Facts with no declared mapping | Normal. They are stored and queryable, just not published |
| `withheld` | An unresolvable unit or turnover scale | **Review.** Add a registry entry with evidence, then `ingest publish` — no re-fetch needed |
| `errors` | Fetch or parse failures | Investigate; a failed company never aborts the batch |

Then review new mappings at `https://<domain>/admin/ingestion`.

### Scheduled refresh

Once a supervised manual run has been reviewed, hand it to Beat:

```sh
aws ssm put-parameter --name /brsrlens/prod/env/NSE_BRSR_SCHEDULE_ENABLED \
  --type String --overwrite --value true
ops/bin/brsrlens-prod run 'systemctl restart brsrlens'
```

Weekly by default (`NSE_BRSR_REFRESH_HOURS=168`), using
`NSE_BRSR_DEFAULT_BATCH_SIZE`. Every run is recorded in `ingestion_runs`.

### Large batches

A cohort-wide reprocess belongs on the batch node, not the app node — extraction
will otherwise take memory the public site needs:

```sh
cd infra/terraform && terraform apply -var enable_batch_node=true
# ... run the batch against BRSRLENS_INSTANCE_ID=$(terraform output -raw batch_instance_id)
terraform apply -var enable_batch_node=false
```

---

## 10. Everyday operations

```sh
ops/bin/brsrlens-prod status              # release, containers, disk, corpus counts
ops/bin/brsrlens-prod logs api 200
ops/bin/brsrlens-prod deploy sha-def5678
ops/bin/brsrlens-prod rollback            # to the recorded previous release
ops/bin/brsrlens-prod backup manual
ops/bin/brsrlens-prod restore list
ops/bin/brsrlens-prod psql "select count(*) from filings"   # read-only transaction
ops/bin/brsrlens-prod shell
```

**Backups** run nightly at 19:30 UTC and before every ingest. A dump smaller than
1 MB is rejected rather than uploaded, because an empty dump would otherwise
rotate a good backup out of retention. Every success publishes a CloudWatch
metric that the dead-man alarm watches, so backups that silently stop running
raise an alarm instead of being discovered during a restore.

**Restore drills** are quarterly. `restore.sh` is the drill.

**Rollback rolls back code only.** Migrations are expand-only by policy, so the
previous release runs against the newer schema. There is no automatic
down-migration and there should not be one during an incident.

---

## 11. Launch checklist

Infrastructure, done by following this document:

- [ ] Sandbox estate applied and destroyed cleanly in a separate account
- [ ] TLS grade A; HSTS present; HTTP redirects
- [ ] SSM-only access verified — no SSH ingress in the app security group
- [ ] SNS email subscription **confirmed**
- [ ] Budget alarm active at the agreed threshold
- [ ] A forced-bad-image deploy auto-rolled back and the alert arrived
- [ ] Restore drill executed against the sandbox, lineage assertions green
- [ ] Corpus counts match expectations and the smoke suite passes
- [ ] `ingest next --limit 1` succeeds end to end on the real node

Product and governance, **not** unblocked by this document:

- [ ] **Legal gate signed** — `docs/gates/legal.md`. Setting
      `SOURCE_NSE_BRSR_ENABLED=true` is the signature's technical expression;
      doing it before the signature inverts the control.
- [ ] **Editorial gate signed** — `docs/gates/editorial.md`. Two decisions are
      open: whether provisional NSE pins may appear on public surfaces, and
      whether the cohort minimum of 5 is right.
- [ ] **UX gate signed** — `docs/gates/ux.md`. Blocked on a browser runtime for
      the visual and keyboard passes.
- [ ] Mapping review started at `/admin/ingestion`, beginning with `MtCO2e`
- [ ] Methodology page live and matching `scoring.yaml`
- [ ] Correction channel tested end to end
- [ ] Lead routing tested to a real inbox
- [ ] On-call owner named; 48-hour watch begins

All three gate files exist and **all three are unsigned**. The build plan is
explicit that there is no launch without them. The infrastructure being ready
does not change that.

---

## Troubleshooting

**`render-env.sh` refuses to run.** A parameter still reads `CHANGE_ME`. The
error lists which ones. This is the guard working.

**Deploy fails at migrations.** The previous release is untouched and still
serving. Read `ops/bin/brsrlens-prod run 'tail -100 /opt/brsrlens/log/deploy.log'`.

**Smoke fails on the corpus assertion, everything else passes.** The database is
empty or was restored without data. Go to step 8. This assertion exists
precisely because an empty database otherwise renders as a site full of "no
data" rather than as an error.

**nginx will not start.** Almost always a missing certificate path. The web
container's entrypoint generates a self-signed placeholder when none exists; if
that failed, check that `/opt/brsrlens/tls` is writable and that `DOMAIN_NAME`
reached the container.

**Ingest refuses with a legal-gate message.** Intended. See step 8, Path A.

**Ingest discovers zero filings from EC2.** See the Path A risk note. This is a
source-side IP restriction, not a code fault.

**SSM command output looks truncated.** SSM caps captured output at 24 KB. Long
deploys and ingests keep the full transcript at `/opt/brsrlens/log/` and in the
CloudWatch log group.

---

## Known gaps

Stated plainly so nobody discovers them during an incident.

- **`terraform plan` has not been run.** The configuration passes
  `terraform fmt -check` and `terraform validate` against AWS provider 5.100.0,
  but no apply has happened against a real account. Expect to fix small things
  on the first plan.
- **Backups are logical dumps, not PITR.** Good for this corpus size and simple
  to restore. RPO is one day, plus any pre-ingest snapshot. The pgBackRest WAL
  archiving described in `DEPLOYMENT.md` section 4 is the upgrade when RPO needs
  to be minutes.
- **Single node, single AZ.** An AZ failure is a restore-from-backup event, not
  a failover. This is the documented trade-off for launch scale; the first moves
  when it stops fitting are in `DEPLOYMENT.md` section 1.
- **The NSE crawl is unproven from AWS.** See step 8.
- **CORS in `api/app/main.py` is pinned to `http://localhost:5173`.** Harmless in
  production, where nginx serves the API on the same origin, but it means no
  other origin can call the API. Change it deliberately if a separate frontend
  host is ever introduced.
- **No CDN.** `DEPLOYMENT.md` names CloudFront as the likely first scaling move
  for a public content product. The prerendered pages and immutable asset
  caching make it a drop-in when needed.
