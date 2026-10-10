"""Small reviewed travel catalog, separated by entity type and versioned."""

import re

from domain.semantic import EntityMember, EntitySetValue
from requirements.normalize import ALIASES, PLACE_PARENTS, fold

CATALOG_VERSION = "tour-entities-v2.3"
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
    "city:cn:shanghai": ["Thượng Hải", "Shanghai"],
    "city:cn:beijing": ["Bắc Kinh", "Beijing"],
    "city:cn:hangzhou": ["Hàng Châu", "Hangzhou"],
    "city:cn:nanjing": ["Nam Kinh", "Nanjing"],
    "city:cn:shenzhen": ["Thẩm Quyến", "Shenzhen"],
    "city:cn:wuzhen": ["Ô Trấn", "Tây Ô Trấn", "Wuzhen"],
    "city:tw:taipei": ["Đài Bắc", "Taipei"],
    "city:tw:taichung": ["Đài Trung", "Taichung"],
    "city:tw:kaohsiung": ["Cao Hùng", "Kaohsiung"],
    "region:tw:nantou": ["Nam Đầu", "Nantou"],
    "country:bn": ["Brunei", "Brunei Darussalam"],
    "city:bn:bandar_seri_begawan": ["Bandar Seri Begawan"],
}
for eid, aliases in PLACE_ENTRIES.items():
    CATALOG["place"].update({fold(alias): eid for alias in aliases})

# Reviewed travel names; city requests retain city IDs rather than becoming countries.
COUNTRY_NAMES = {
    "fr": ["Pháp", "France"],
    "ch": ["Thụy Sĩ", "Switzerland"],
    "it": ["Ý", "Italia", "Italy"],
    "va": ["Vatican"],
    "be": ["Bỉ", "Belgium"],
    "nl": ["Hà Lan", "Netherlands"],
    "de": ["Đức", "Germany"],
    "at": ["Áo", "Austria"],
    "gb": ["Anh", "Anh Quốc", "United Kingdom", "England"],
    "au": ["Úc", "Australia"],
    "us": ["Mỹ", "Hoa Kỳ", "United States", "USA"],
    "ca": ["Canada"],
    "my": ["Malaysia"],
    "id": ["Indonesia"],
    "kh": ["Campuchia", "Cambodia", "Cam-pu-chia"],
    "la": ["Lào", "Laos"],
    "tr": ["Thổ Nhĩ Kỳ", "Turkey", "Türkiye"],
    "bt": ["Bhutan"],
    "in": ["Ấn Độ", "India"],
    "np": ["Nepal"],
    "ae": ["UAE", "Các Tiểu Vương Quốc Ả Rập Thống Nhất"],
    "fi": ["Phần Lan", "Finland"],
    "no": ["Na Uy", "Norway"],
    "se": ["Thụy Điển", "Sweden"],
    "dk": ["Đan Mạch", "Denmark"],
    "cz": ["Séc", "Cộng Hòa Séc", "Czech Republic"],
    "es": ["Tây Ban Nha", "Spain"],
    "pt": ["Bồ Đào Nha", "Portugal"],
    "gr": ["Hy Lạp", "Greece"],
    "nz": ["New Zealand"],
    "za": ["Nam Phi", "South Africa"],
    "eg": ["Ai Cập", "Egypt"],
    "ru": ["Nga", "Russia"],
    "mn": ["Mông Cổ", "Mongolia"],
}
CITY_NAMES = {
    "fr:paris": ["Paris"],
    "fr:lille": ["Lille"],
    "fr:reims": ["Reims"],
    "be:brussels": ["Brussels", "Bruxelles"],
    "nl:amsterdam": ["Amsterdam"],
    "de:munich": ["Munich", "München"],
    "de:frankfurt": ["Frankfurt"],
    "at:vienna": ["Vienna", "Wien"],
    "it:rome": ["Rome", "Roma"],
    "it:venice": ["Venice", "Venezia"],
    "it:milan": ["Milan", "Milano"],
    "ch:zurich": ["Zurich", "Zürich"],
    "ch:geneva": ["Geneva", "Genève"],
    "gb:london": ["London"],
    "gb:oxford": ["Oxford"],
    "gb:birmingham": ["Birmingham"],
    "ca:toronto": ["Toronto"],
    "ca:vancouver": ["Vancouver"],
    "au:sydney": ["Sydney"],
    "au:melbourne": ["Melbourne"],
    "kh:phnompenh": ["Phnom Penh", "Phnompenh"],
    "kh:siemreap": ["Siem Reap"],
    "my:kualalumpur": ["Kuala Lumpur"],
    "bt:paro": ["Paro"],
    "bt:thimphu": ["Thimphu"],
    "bt:punakha": ["Punakha"],
    "fi:helsinki": ["Helsinki"],
    "no:oslo": ["Oslo"],
    "se:stockholm": ["Stockholm"],
    "dk:copenhagen": ["Copenhagen"],
    "cz:prague": ["Prague", "Praha"],
    "jp:kobe": ["Kobe"],
    "jp:nara": ["Nara"],
    "jp:uji": ["Uji"],
    "vn:cantho": ["Cần Thơ"],
    "vn:ninhbinh": ["Ninh Bình"],
    "vn:halong": ["Hạ Long", "Ha Long"],
    "vn:phuquoc": ["Phú Quốc", "Phu Quoc"],
    "vn:phanthiet": ["Phan Thiết"],
    "vn:hoian": ["Hội An", "Hoi An"],
    "vn:camau": ["Cà Mau"],
    "vn:sapa": ["Sa Pa", "Sapa"],
    "vn:vungtau": ["Vũng Tàu"],
    "vn:tay-ninh": ["Tây Ninh"],
    "vn:vinh": ["Vinh"],
    "vn:phanrang": ["Phan Rang"],
}
EXTRA_PLACES = {
    "region:id:bali": ["Bali"],
    "region:vn:con_dao": ["Côn Đảo"],
    **{"country:" + code: names for code, names in COUNTRY_NAMES.items()},
    **{"city:" + code: names for code, names in CITY_NAMES.items()},
    "region:cn:hongkong": ["Hồng Kông", "Hong Kong", "HongKong"],
    "region:jp:yamanashi": ["Yamanashi"],
    "region:jp:shiga": ["Shiga"],
    "region:jp:fuji": ["Fuji", "Núi Phú Sĩ", "Phú Sĩ"],
    "region:vn:quangninh": ["Quảng Ninh"],
    "region:vn:laocai": ["Lào Cai"],
    "region:vn:quangnam": ["Quảng Nam"],
    "region:vn:mekong": ["Miền Tây", "Đồng Bằng Sông Cửu Long"],
}
for eid, aliases in EXTRA_PLACES.items():
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
for eid in PLACE_ENTRIES:
    if eid.startswith(("city:cn:", "city:tw:", "region:tw:", "city:bn:")):
        PLACE_RELATIONS[eid] = {"country:" + eid.split(":")[1]}
for eid in EXTRA_PLACES:
    if eid.startswith(("city:", "region:")):
        PLACE_RELATIONS[eid] = {"country:" + eid.split(":")[1]}
TRANSPORT_RELATIONS = {"car": {"motor_vehicle"}, "coach": {"motor_vehicle"}, "minibus": {"motor_vehicle"}}


def split_place_values(values):
    result = []
    for raw in values:
        if fold(raw) in CATALOG["place"]:
            result.append(raw)
        else:
            # A separator must have spaces on both sides; do not split compound names.
            result.extend(x.strip() for x in re.split(r"\s+[–—-]\s+", raw) if x.strip())
    return result


def resolve_entities(field, raw_values):
    kind = TYPE_BY_FIELD[field]
    if kind == "place":
        raw_values = split_place_values(raw_values)
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
