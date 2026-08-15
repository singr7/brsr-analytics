from api.app.schemas.nlq import ContextProvenance
from api.app.schemas.semantic import SemanticQuery


def merge_context(
    base: SemanticQuery | None, translated: SemanticQuery
) -> tuple[SemanticQuery, ContextProvenance]:
    """Merge visible context with a translation before central validation and policy.

    A follow-up's filters override the same base dimension; every other visible filter is
    inherited. The translated analytical intent (measure, grouping and shape) remains explicit.
    """
    if base is None:
        return translated, ContextProvenance()
    translated_dimensions = {item.dimension for item in translated.filters}
    inherited = [item for item in base.filters if item.dimension not in translated_dimensions]
    merged = translated.model_copy(update={"filters": [*inherited, *translated.filters]})
    return merged, ContextProvenance(
        applied=True,
        inherited_filters=[item.dimension for item in inherited],
        overridden_filters=sorted(
            {item.dimension for item in base.filters} & translated_dimensions
        ),
    )
