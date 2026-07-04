from dataclasses import dataclass, field


@dataclass(slots=True)
class ContentCatalogData:
    resources: dict[object, list[object]] = field(default_factory=dict)
