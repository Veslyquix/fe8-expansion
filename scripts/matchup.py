import json


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
]

# Weapon assignment for each class
CLASS_WEAPONS = {
    "CLASS_SOLDIER": "ITEM_LANCE_IRON",
    "CLASS_ARMOR_KNIGHT": "ITEM_LANCE_IRON",
    "CLASS_ARCHER": "ITEM_BOW_IRON",
    "CLASS_CAVALIER": "ITEM_SWORD_IRON",
    "CLASS_FIGHTER": "ITEM_AXE_IRON",
    "CLASS_MERCENARY": "ITEM_SWORD_IRON",
    "CLASS_MAGE": "ITEM_ANIMA_FIRE",
}

# Fire Emblem doubling threshold
DOUBLE_SPEED_DIFFERENCE = 4


# ============================================================
# JSON FUNCTIONS
# ============================================================

def load_json(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


def find_by_field(entries, field, value):
    for entry in entries:
        if entry.get(field) == value:
            return entry
    return None


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

def calculate_wta(weapon, defender_weapon):
    attacker_type = weapon.get("weaponType")
    defender_type = defender_weapon.get("weaponType")

    advantages = {
        "ITYPE_SWORD": "ITYPE_AXE",
        "ITYPE_AXE": "ITYPE_LANCE",
        "ITYPE_LANCE": "ITYPE_SWORD",
    }

    # Attacker has weapon triangle advantage
    if advantages.get(attacker_type) == defender_type:
        return 1

    # Defender has weapon triangle advantage
    if advantages.get(defender_type) == attacker_type:
        return -1

    # No weapon triangle interaction
    return 0

def calculate_single_hit_damage(attacker_class, weapon, defender_class, defender_weapon):
    attacker_pow = attacker_class["base"]["pow"]
    weapon_might = weapon.get("might", 0)

    target_defense, defense_name = get_target_defense(
        weapon,
        defender_class
    )
    attacker_pow += calculate_wta(weapon, defender_weapon) 

    damage = max(
        0,
        attacker_pow + weapon_might - target_defense
    )

    return damage, defense_name


def can_double(attacker_class, defender_class):
    attacker_spd = attacker_class["base"]["spd"]
    defender_spd = defender_class["base"]["spd"]

    return attacker_spd >= defender_spd + DOUBLE_SPEED_DIFFERENCE


def calculate_round(attacker_class, attacker_weapon,
                    defender_class, defender_weapon):

    # Damage for each direction
    attacker_hit_damage, attacker_defense_type = (
        calculate_single_hit_damage(
            attacker_class,
            attacker_weapon,
            defender_class,
            defender_weapon
        )
    )

    defender_hit_damage, defender_defense_type = (
        calculate_single_hit_damage(
            defender_class,
            defender_weapon,
            attacker_class,
            defender_weapon
        )
    )

    # Check doubling
    attacker_doubles = can_double(
        attacker_class,
        defender_class
    )

    defender_doubles = can_double(
        defender_class,
        attacker_class
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
                  class_b_name, class_b, weapon_b_name, weapon_b):

    result = calculate_round(
        class_a,
        weapon_a,
        class_b,
        weapon_b
    )

    # Remove CLASS_ from the names
    class_a_display = class_a_name.replace("CLASS_", "")
    class_b_display = class_b_name.replace("CLASS_", "")

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

    print(
        f"{class_a_display} vs {class_b_display}: "
##        f"{result['attacker_hit_damage']}x{result['attacker_hits']} "
        f"{class_a_percent:.0f}% vs "
##        f"{result['defender_hit_damage']}x{result['defender_hits']} "
        f"{class_b_percent:.0f}%"
    )

# ============================================================
# MAIN
# ============================================================

def main():

    # Load JSON files
    classes_data = load_json(
        "../src/data/classes.json"
    )

    items_data = load_json(
        "../src/data/items.json"
    )

    classes = classes_data["classes"]
    items = items_data["items"]

    # Build lookup dictionaries
    class_lookup = {
        entry["class"]: entry
        for entry in classes
    }

    item_lookup = {
        entry["item"]: entry
        for entry in items
    }

    # Validate all requested classes and weapons
    for class_name in CLASSES_TO_TEST:

        if class_name not in class_lookup:
            print(f"ERROR: Class not found: {class_name}")
            return

        weapon_name = CLASS_WEAPONS[class_name]

        if weapon_name not in item_lookup:
            print(f"ERROR: Item not found: {weapon_name}")
            return

    # Run every unique matchup
    for i, class_a_name in enumerate(CLASSES_TO_TEST):

        for class_b_name in CLASSES_TO_TEST[i + 1:]:

            weapon_a_name = CLASS_WEAPONS[class_a_name]
            weapon_b_name = CLASS_WEAPONS[class_b_name]

            print_matchup(
                class_a_name,
                class_lookup[class_a_name],
                weapon_a_name,
                item_lookup[weapon_a_name],

                class_b_name,
                class_lookup[class_b_name],
                weapon_b_name,
                item_lookup[weapon_b_name]
            )


if __name__ == "__main__":
    main()
