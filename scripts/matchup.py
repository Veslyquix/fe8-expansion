import re

EXPAND_DETAILS = True  

# ============================================================
# CONFIGURATION
# ============================================================

CLASSES_TO_TEST = [
    "CLASS_SOLDIER",
    "CLASS_ARMOR_KNIGHT",
    "CLASS_ARCHER",
    "CLASS_CAVALIER",
    "CLASS_FIGHTER",
    "CLASS_MERCENARY",
    "CLASS_MAGE",
    "CLASS_PEGASUS_KNIGHT",
]

# Weapon(s) assigned to each class. Most classes get one weapon, but a
# class with access to multiple weapon types (e.g. Cavalier) can list more
# than one -- every listed weapon is tested against every matchup.
CLASS_WEAPONS = {
    "CLASS_SOLDIER": ["ITEM_LANCE_IRON"],
    "CLASS_ARMOR_KNIGHT": ["ITEM_LANCE_IRON"],
    "CLASS_ARCHER": ["ITEM_BOW_IRON"],
    "CLASS_CAVALIER": ["ITEM_SWORD_IRON", "ITEM_LANCE_IRON", "ITEM_AXE_IRON"],
    "CLASS_FIGHTER": ["ITEM_AXE_IRON"],
    "CLASS_MERCENARY": ["ITEM_SWORD_IRON"],
    "CLASS_MAGE": ["ITEM_ANIMA_FIRE"],
    "CLASS_PEGASUS_KNIGHT": ["ITEM_LANCE_IRON"]
}

# Fire Emblem doubling threshold
DOUBLE_SPEED_DIFFERENCE = 4

CLASSES_C_PATH = "../src/data_classes.c"
ITEMS_C_PATH = "../src/data_items.c"
WEAPON_TRIANGLE_C_PATH = "../src/bmbattle.c"


# ============================================================
# C SOURCE PARSING
# ============================================================
#
# These files are the hand-written tables the modern build actually
# compiles (see docs, "unlink json things") -- classes.json/items.json/
# weapontriangle.json are no longer the build's source of truth, so this
# script reads the same C the ROM links instead of the JSON siblings.
# Parsing is deliberately simple regex/brace-matching, not a real C
# parser: it only needs to survive the flat designated-initializer shape
# these tables actually use.

def _find_matching_brace(text, open_index):
    depth = 0
    for i in range(open_index, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("unbalanced braces starting at %d" % open_index)


def parse_designated_array(path, key_pattern):
    """Parse `[KEY] = { .field = value, ... },` entries into
    {key: {field: value_str}}. Ignores fields whose value is itself a
    brace-enclosed initializer (nested structs/arrays aren't needed here)."""
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    entries = {}
    for m in re.finditer(key_pattern + r"\s*=\s*\{", text):
        key = m.group(1)
        open_brace = m.end() - 1
        close_brace = _find_matching_brace(text, open_brace)
        body = text[open_brace + 1:close_brace]

        fields = {}
        for fm in re.finditer(r"\.(\w+)\s*=\s*([^,{}]+),", body):
            fields[fm.group(1)] = fm.group(2).strip()
        entries[key] = fields

    return entries


def parse_int(value_str):
    value_str = value_str.strip()
    try:
        return int(value_str, 0)
    except ValueError:
        return value_str


def load_classes(path=CLASSES_C_PATH):
    raw = parse_designated_array(path, r"\[(CLASS_\w+)(?:\s*-\s*1)?\]")

    classes = {}
    for class_name, fields in raw.items():
        classes[class_name] = {
            "base": {
                "hp": parse_int(fields.get("baseHP", "0")),
                "pow": parse_int(fields.get("basePow", "0")),
                "skl": parse_int(fields.get("baseSkl", "0")),
                "spd": parse_int(fields.get("baseSpd", "0")),
                "def": parse_int(fields.get("baseDef", "0")),
                "res": parse_int(fields.get("baseRes", "0")),
                "con": parse_int(fields.get("baseCon", "0")),
                "mov": parse_int(fields.get("baseMov", "0")),
            },
        }

    return classes


def load_items(path=ITEMS_C_PATH):
    raw = parse_designated_array(path, r"\[(ITEM_\w+)\]")

    items = {}
    for item_name, fields in raw.items():
        items[item_name] = {
            "weaponType": fields.get("weaponType"),
            "might": parse_int(fields.get("might", "0")),
            "weight": parse_int(fields.get("weight", "0")),
        }

    return items


def load_weapon_triangle(path=WEAPON_TRIANGLE_C_PATH):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    m = re.search(
        r"sWeaponTriangleRules\[\]\s*=\s*\{(.*?)\n\};",
        text,
        re.DOTALL,
    )
    if not m:
        raise ValueError("sWeaponTriangleRules not found in %s" % path)

    body = m.group(1)

    rules = []
    for rm in re.finditer(
        r"\{\s*(ITYPE_\w+)\s*,\s*(ITYPE_\w+)\s*,\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\}",
        body,
    ):
        rules.append({
            "attackerWeaponType": rm.group(1),
            "defenderWeaponType": rm.group(2),
            "hitBonus": int(rm.group(3)),
            "atkBonus": int(rm.group(4)),
        })

    return rules


# ============================================================
# COMBAT FUNCTIONS
# ============================================================

def is_magic_weapon(weapon):
    magic_types = [
        "ITYPE_ANIMA",
        "ITYPE_LIGHT",
        "ITYPE_DARK"
    ]

    return weapon.get("weaponType") in magic_types


def get_target_defense(weapon, defender_class):
    if is_magic_weapon(weapon):
        return defender_class["base"]["res"], "RES"

    return defender_class["base"]["def"], "DEF"

def calculate_wta(weapon, defender_weapon, weapon_triangle_rules):
    attacker_type = weapon.get("weaponType")
    defender_type = defender_weapon.get("weaponType")

    for rule in weapon_triangle_rules:
        if (rule["attackerWeaponType"] == attacker_type
                and rule["defenderWeaponType"] == defender_type):
            return rule["atkBonus"]

    return 0


def calculate_single_hit_damage(attacker_class, weapon, defender_class, defender_weapon, weapon_triangle_rules):
    attacker_pow = attacker_class["base"]["pow"]
    weapon_might = weapon.get("might", 0)

    target_defense, defense_name = get_target_defense(
        weapon,
        defender_class
    )
    attacker_pow += calculate_wta(weapon, defender_weapon, weapon_triangle_rules)

    damage = max(
        0,
        attacker_pow + weapon_might - target_defense
    )

    return damage, defense_name


def get_effective_speed(cls, weapon):
    """Weapon weight over the wielder's own con drags speed down 1-for-1
    (e.g. a 9-con Cavalier with a 10-weight Iron Axe: 10 - 9 = 1 overweight,
    so their effective spd is base spd - 1)."""
    overweight = max(0, weapon.get("weight", 0) - cls["base"]["con"])
    return cls["base"]["spd"] - overweight


def can_double(attacker_class, attacker_weapon, defender_class, defender_weapon):
    attacker_spd = get_effective_speed(attacker_class, attacker_weapon)
    defender_spd = get_effective_speed(defender_class, defender_weapon)

    return attacker_spd >= defender_spd + DOUBLE_SPEED_DIFFERENCE


def calculate_round(attacker_class, attacker_weapon,
                    defender_class, defender_weapon, weapon_triangle_rules):

    # Damage for each direction
    attacker_hit_damage, attacker_defense_type = (
        calculate_single_hit_damage(
            attacker_class,
            attacker_weapon,
            defender_class,
            defender_weapon,
            weapon_triangle_rules
        )
    )

    defender_hit_damage, defender_defense_type = (
        calculate_single_hit_damage(
            defender_class,
            defender_weapon,
            attacker_class,
            attacker_weapon,
            weapon_triangle_rules
        )
    )

    # Check doubling
    attacker_doubles = can_double(
        attacker_class,
        attacker_weapon,
        defender_class,
        defender_weapon
    )

    defender_doubles = can_double(
        defender_class,
        defender_weapon,
        attacker_class,
        attacker_weapon
    )

    # Number of hits
    attacker_hits = 2 if attacker_doubles else 1
    defender_hits = 2 if defender_doubles else 1

    # Total damage
    attacker_total_damage = (
        attacker_hit_damage * attacker_hits
    )

    defender_total_damage = (
        defender_hit_damage * defender_hits
    )

    return {
        "attacker_hit_damage": attacker_hit_damage,
        "defender_hit_damage": defender_hit_damage,

        "attacker_hits": attacker_hits,
        "defender_hits": defender_hits,

        "attacker_total_damage": attacker_total_damage,
        "defender_total_damage": defender_total_damage,

        "attacker_doubles": attacker_doubles,
        "defender_doubles": defender_doubles,

        "attacker_defense_type": attacker_defense_type,
        "defender_defense_type": defender_defense_type,
    }


# ============================================================
# DISPLAY
# ============================================================

def print_matchup(class_a_name, class_a, weapon_a_name, weapon_a,
                  class_b_name, class_b, weapon_b_name, weapon_b,
                  weapon_triangle_rules):

    result = calculate_round(
        class_a,
        weapon_a,
        class_b,
        weapon_b,
        weapon_triangle_rules
    )

    # Remove CLASS_ from the names
    class_a_display = class_a_name.replace("CLASS_", "")
    class_b_display = class_b_name.replace("CLASS_", "")

    # Only disambiguate with the weapon when the class has more than one
    # weapon option -- keeps single-weapon classes' output unchanged.
    if len(CLASS_WEAPONS[class_a_name]) > 1:
        class_a_display += " (%s)" % weapon_a_name.replace("ITEM_", "")
    if len(CLASS_WEAPONS[class_b_name]) > 1:
        class_b_display += " (%s)" % weapon_b_name.replace("ITEM_", "")

    # Percentage of the target's HP dealt during the round
    class_a_percent = (
        result["attacker_total_damage"]
        / class_b["base"]["hp"]
        * 100
    )

    class_b_percent = (
        result["defender_total_damage"]
        / class_a["base"]["hp"]
        * 100
    )
    if EXPAND_DETAILS:
            print(
            f"{class_a_display} vs {class_b_display}: "
            f"{result['attacker_hit_damage']}x{result['attacker_hits']} "
            f"{class_a_percent:.0f}% vs "
            f"{result['defender_hit_damage']}x{result['defender_hits']} "
            f"{class_b_percent:.0f}% "
        )
    else:
        print(
            f"{class_a_display} vs {class_b_display}: "
            f"{class_a_percent:.0f}% vs "
            f"{class_b_percent:.0f}% "
        )

# ============================================================
# MAIN
# ============================================================

def main():

    # Load data straight from the hand C tables the build actually links.
    classes = load_classes()
    items = load_items()
    weapon_triangle_rules = load_weapon_triangle()

    # Validate all requested classes and weapons
    for class_name in CLASSES_TO_TEST:

        if class_name not in classes:
            print(f"ERROR: Class not found: {class_name}")
            return

        for weapon_name in CLASS_WEAPONS[class_name]:
            if weapon_name not in items:
                print(f"ERROR: Item not found: {weapon_name}")
                return

    # Run every matchup as seen from each class's perspective (including
    # the mirror match), across every weapon each class has access to,
    # grouped by attacker so repeats stay easy to scan.
    for class_a_name in CLASSES_TO_TEST:

        for weapon_a_name in CLASS_WEAPONS[class_a_name]:

            for class_b_name in CLASSES_TO_TEST:

                for weapon_b_name in CLASS_WEAPONS[class_b_name]:

                    print_matchup(
                        class_a_name,
                        classes[class_a_name],
                        weapon_a_name,
                        items[weapon_a_name],

                        class_b_name,
                        classes[class_b_name],
                        weapon_b_name,
                        items[weapon_b_name],

                        weapon_triangle_rules
                    )

            print()


if __name__ == "__main__":
    main()
