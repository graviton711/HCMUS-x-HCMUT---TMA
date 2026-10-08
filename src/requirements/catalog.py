"""Small reviewed travel catalog, separated by entity type and versioned."""

from domain.semantic import EntityMember, EntitySetValue
from requirements.normalize import ALIASES, PLACE_PARENTS, fold

CATALOG_VERSION = "tour-entities-v2.1"
TYPE_BY_FIELD = {
    "destinations": "place",
    "departure_origin": "place",
    "route": "place",
    "transport": "transport",
    "included_services": "service",
    "supplier": "supplier",
    "tour_type": "tour_type",
}
CATALOG = {kind: {} for kind in TYPE_BY_FIELD.values()}
for alias, eid in ALIASES.items():
    kind = "place" if ":" in eid else "transport" if eid in {"flight", "coach", "train"} else "service"
    CATALOG[kind][alias] = eid

PLACE_ENTRIES = {
    "city:vn:haiphong": ["Hải Phòng", "Hai Phong", "TP Hải Phòng", "thành phố Hải Phòng"],
    "region:vn:central_highlands": ["Tây Nguyên", "Tay Nguyen", "Central Highlands"],
    "city:vn:hue": ["Huế", "Hue"],
    "city:vn:dalat": ["Đà Lạt", "Da Lat"],
    "city:vn:buonmathuot": ["Buôn Ma Thuột", "Buon Ma Thuot"],
    "city:vn:quynhon": ["Quy Nhơn", "Quy Nhon"],
    "city:vn:nhatrang": ["Nha Trang"],
}
for eid, aliases in PLACE_ENTRIES.items():
    CATALOG["place"].update({fold(alias): eid for alias in aliases})
CATALOG["transport"].update(
    {
        "xe o to": "motor_vehicle",
        "o to": "motor_vehicle",
        "automobile": "motor_vehicle",
        "xe con": "car",
        "car": "car",
        "minibus": "minibus",
        "xe buyt": "coach",
    }
)
CATALOG["tour_type"].update(
    {
        "ghep doan": "join_group",
        "tour ghep doan": "join_group",
        "du lich ghep doan": "join_group",
        "tour rieng": "private_group",
        "doan rieng": "private_group",
    }
)
PLACE_RELATIONS = {key: {parent} for key, parent in PLACE_PARENTS.items()}
PLACE_RELATIONS.update(
    {
        "city:vn:haiphong": {"country:vn"},
        "region:vn:central_highlands": {"country:vn"},
        "city:vn:hue": {"region:vn:central"},
        "city:vn:dalat": {"region:vn:central_highlands"},
        "city:vn:buonmathuot": {"region:vn:central_highlands"},
        "city:vn:quynhon": {"region:vn:central"},
        "city:vn:nhatrang": {"region:vn:central"},
    }
)
TRANSPORT_RELATIONS = {"car": {"motor_vehicle"}, "coach": {"motor_vehicle"}, "minibus": {"motor_vehicle"}}


def resolve_entities(field, raw_values):
    kind = TYPE_BY_FIELD[field]
    members, seen = [], set()
    for raw in raw_values:
        eid = CATALOG[kind].get(fold(raw))
        key = eid or fold(raw)
        if key in seen:
            continue
        seen.add(key)
        members.append(
            EntityMember(
                raw=raw, entity_type=kind, entity_id=eid, status="resolved" if eid else "catalog_missing"
            )
        )
    return EntitySetValue(members=members, catalog_version=CATALOG_VERSION)


def expand_entities(items, kind):
    result, pending = set(items), list(items)
    relations = TRANSPORT_RELATIONS if kind == "transport" else PLACE_RELATIONS if kind == "place" else {}
    while pending:
        item = pending.pop()
        for parent in relations.get(item, ()):
            if parent not in result:
                result.add(parent)
                pending.append(parent)
    return result


def known_entity_ids(kind):
    relations = TRANSPORT_RELATIONS if kind == "transport" else PLACE_RELATIONS if kind == "place" else {}
    return (
        set(CATALOG[kind].values())
        | set(relations)
        | {parent for parents in relations.values() for parent in parents}
    )
