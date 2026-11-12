"""The car classes a clan tag can name, for a multi-class race, and their colours.

Drivers name their car's class with their clan tag in TSU ([GT3], [LMP], ...; asked for by the
user on 2026-11-11). TSU keeps the tag without its brackets ('GT3') and allows 5 characters.
A tag counts as a class only when it is one of the codes below (or the settings file's own
list), compared without brackets or spaces and in any case: `[GrT]`, `GRT` and `grt` are all
Group Touring. Any other tag is a team's tag and stays one.

Each class belongs to a category, and the category gives it its colour in the lap times
(asked for by the user on 2026-11-12). Two classes of one category in the same race still
look different: see class_colors.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    name: str
    color: str  # '#rrggbb'


# In this order: a class whose category's colour is taken looks for the next free one here.
PROTOTYPE = Category('Prototype & Endurance', '#805AD5')
GT = Category('GT & Sports Cars', '#2586CC')
FORMULA = Category('Formula & Open Wheel', '#D9514B')
TOURING = Category('Touring & Production', '#269B76')
STOCK = Category('Stock & Oval', '#D69635')
RALLY = Category('Rally & Off-Road', '#BC6747')
ONE_MAKE = Category('One-Make & Manufacturer', '#D6A238')
CUSTOM = Category('Custom & Special', '#7E879A')
CATEGORIES = (PROTOTYPE, GT, FORMULA, TOURING, STOCK, RALLY, ONE_MAKE, CUSTOM)


@dataclass(frozen=True)
class CarClass:
    code: str  # as shown, such as 'GrT'; compared in capitals (class_tag)
    name: str
    category: Category


def _classes(category, *pairs):
    return tuple(CarClass(code, name, category) for code, name in pairs)


# In this order within a category, a class keeps the category's colour before the ones after
# it (GT3 before GT4). Besides the user's list, the class tags from before the categories
# (2026-11-11), the long ones shortened by the user on 2026-11-12: LMDH as LDH, LMP1 to LMP3 as
# LM1 to LM3, GTLM as GLM; HYPER dropped (HYP stays). PRO, AM, PROAM and SILV are still as before.
CLASSES = (
    *_classes(
        PROTOTYPE,
        ('HYP', 'Hypercar'),
        ('LMH', 'Le Mans Hypercar'),
        ('LMD', 'LMDh Prototype'),
        ('LDH', 'LMDh Prototype'),
        ('GTP', 'Grand Touring Prototype'),
        ('LMP', 'Le Mans Prototype'),
        ('LM1', 'Le Mans Prototype 1'),
        ('LM2', 'Le Mans Prototype 2'),
        ('LM3', 'Le Mans Prototype 3'),
        ('P1', 'Prototype 1'),
        ('P2', 'Prototype 2'),
        ('P3', 'Prototype 3'),
        ('DPI', 'Daytona Prototype International'),
        ('SRP', 'Sports Racing Prototype'),
        ('CN', 'CN Prototype'),
    ),
    *_classes(
        GT,
        ('GT', 'Grand Touring'),
        ('GT1', 'Grand Touring 1'),
        ('GT2', 'Grand Touring 2'),
        ('GT3', 'Grand Touring 3'),
        ('GT4', 'Grand Touring 4'),
        ('GT5', 'Grand Touring 5'),
        ('GTE', 'GT Endurance'),
        ('GLM', 'GT Le Mans'),
        ('GTD', 'GT Daytona'),
        ('GTC', 'GT Cup'),
        ('GTX', 'GT Experimental'),
        ('GTS', 'GT Sport'),
        ('SGT', 'Super GT'),
        ('GTO', 'GT Over'),
        ('GTU', 'GT Under'),
        ('GR5', 'Group 5'),
    ),
    *_classes(
        FORMULA,
        ('F1', 'Formula 1'),
        ('F2', 'Formula 2'),
        ('F3', 'Formula 3'),
        ('F4', 'Formula 4'),
        ('FE', 'Formula E'),
        ('FF', 'Formula Ford'),
        ('FV', 'Formula Vee'),
        ('FR', 'Formula Renault'),
        ('SF', 'Super Formula'),
        ('SFL', 'Super Formula Lights'),
        ('IND', 'IndyCar'),
        ('KRT', 'Karting'),
    ),
    *_classes(
        TOURING,
        ('GrT', 'Group Touring'),
        ('TCR', 'Touring Car Racing'),
        ('TC', 'Touring Car'),
        ('TCX', 'Touring Car X'),
        ('TCA', 'Touring Car A'),
        ('TCB', 'Touring Car B'),
        ('DTM', 'Deutsche Tourenwagen Masters'),
        ('ST', 'Super Touring'),
        ('S2K', 'Super 2000'),
        ('BTC', 'British Touring Car'),
        ('V8S', 'V8 Supercars'),
        ('PRD', 'Production Cars'),
        ('CLB', 'Club Racing'),
    ),
    *_classes(
        STOCK,
        ('CUP', 'Cup Stock Cars'),
        ('XFN', 'Xfinity Stock Cars'),
        ('TRK', 'Racing Trucks'),
        ('ARC', 'ARCA Stock Cars'),
        ('LMS', 'Late Model Stock Cars'),
        ('SLM', 'Super Late Models'),
        ('MOD', 'Modified Stock Cars'),
        ('STK', 'Stock Cars'),
        ('SSC', 'Super Stock Cars'),
        ('LEG', 'Legends Cars'),
    ),
    *_classes(
        RALLY,
        ('R1', 'Rally 1'),
        ('R2', 'Rally 2'),
        ('R3', 'Rally 3'),
        ('R4', 'Rally 4'),
        ('R5', 'Rally 5'),
        ('RX1', 'Rallycross 1'),
        ('RX2', 'Rallycross 2'),
        ('RX3', 'Rallycross 3'),
        ('WRX', 'World Rallycross'),
        ('GRA', 'Group A'),
        ('GRB', 'Group B'),
        ('GRN', 'Group N'),
        ('T1', 'Cross-Country Prototype'),
        ('T2', 'Cross-Country Production'),
        ('T3', 'Lightweight Off-Road Prototype'),
        ('T4', 'Side-by-Side Off-Road'),
        ('UTV', 'Utility Terrain Vehicle'),
    ),
    *_classes(
        ONE_MAKE,
        ('MIN', 'Mini'),
        ('MUS', 'Mustang'),
        ('MX5', 'Mazda MX-5'),
        ('GT8', 'Toyota GT86'),
        ('GR8', 'Toyota GR86'),
        ('SUP', 'Toyota Supra'),
        ('COR', 'Corvette'),
        ('CAM', 'Camaro'),
        ('CHL', 'Challenger'),
        ('VIP', 'Viper'),
        ('911', 'Porsche 911'),
        ('CAY', 'Porsche Cayman'),
        ('BMW', 'BMW'),
        ('M2', 'BMW M2'),
        ('M3', 'BMW M3'),
        ('AMG', 'Mercedes-AMG'),
        ('FER', 'Ferrari'),
        ('LAM', 'Lamborghini'),
        ('RAD', 'Radical'),
        ('CAT', 'Caterham'),
        ('LOT', 'Lotus'),
        ('CLI', 'Clio Cup'),
        ('CIV', 'Honda Civic'),
        ('NIS', 'Nissan GT-R'),
    ),
    *_classes(
        CUSTOM,
        ('UGT', 'Ultimate GT'),
        ('GTR', 'GT Racing'),
        ('GRS', 'Group Sport'),
        ('GRP', 'Group Prototype'),
        ('GRX', 'Group Extreme'),
        ('HST', 'Historic Touring'),
        ('HGT', 'Historic GT'),
        ('HPR', 'Historic Prototype'),
        ('STR', 'Street Racing'),
        ('TUN', 'Tuned Cars'),
        ('UNL', 'Unlimited'),
        ('EV', 'Electric Vehicles'),
        ('HYB', 'Hybrid'),
        ('EXP', 'Experimental'),
        ('PRO', 'Pro'),
        ('AM', 'Am'),
        ('PROAM', 'Pro-Am'),
        ('SILV', 'Silver'),
    ),
)
MAX_CLASS_TAG = 5  # characters: TSU's limit for a clan tag


def class_tag(text):
    """A clan tag as a class code is compared: without brackets or spaces, in capitals."""
    return text.strip().strip('[]()').strip().upper() if isinstance(text, str) else ''


BY_TAG = {class_tag(car_class.code): car_class for car_class in CLASSES}
CLASS_TAGS = tuple(BY_TAG)  # every code, compared as class_tag gives it


def car_class(tag):
    """The CarClass a class code names (in any case, with or without brackets); a code from
    the settings file's own list that is not in CLASSES is of the custom category."""
    code = class_tag(tag)
    return BY_TAG.get(code) or CarClass(code, code, CUSTOM)


def shown_code(tag):
    """How a class code is shown: as in CLASSES ('GrT'), or in capitals."""
    return car_class(tag).code


def class_colors(tags):
    """{class code: '#rrggbb'} for the classes `tags` (as class_tag gives them) in one race.

    In each category the class first in CLASSES (GT3 before GT4) has the category's colour;
    each other class has the next category's colour, in CATEGORIES' order and round, that
    no class in the race has (asked for by the user on 2026-11-12, so GT3 and GT4 differ).
    With more classes than colours, the rest have their own category's colour."""
    order = {tag: index for index, tag in enumerate(CLASS_TAGS)}
    present = sorted(set(tags), key=lambda tag: (order.get(tag, len(order)), tag))
    colors, taken = {}, set()
    for tag in present:  # the first class of each category keeps its colour
        category = car_class(tag).category
        if category.color not in taken:
            colors[tag] = category.color
            taken.add(category.color)
    for tag in present:
        if tag in colors:
            continue
        start = CATEGORIES.index(car_class(tag).category)
        free = [CATEGORIES[(start + step) % len(CATEGORIES)].color for step in range(1, len(CATEGORIES))]
        color = next((color for color in free if color not in taken), car_class(tag).category.color)
        colors[tag] = color
        taken.add(color)
    return colors


INFERRED_PALER = 0.5  # how far towards white: a class a driver is given by their car


def paler(color, share=INFERRED_PALER):
    """'#rrggbb' mixed that far (0 to 1) with white: the colour of a class a driver has
    from their car, not from their own clan tag."""
    channels = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return '#' + ''.join(f'{round(c + (255 - c) * share):02x}' for c in channels)


def sheet_columns(count=5):
    """CATEGORIES in at most `count` columns for the class sheet (turbohud.overlay.class_sheet),
    in their order, with the longest column as short as can be: [[(category, its classes), ...], ...]."""
    groups = [(category, [c for c in CLASSES if c.category == category]) for category in CATEGORIES]
    sizes = [len(classes) + 2 for _category, classes in groups]  # with its heading and a gap

    def split(most):
        """The categories in order, a new column whenever the next would pass `most` lines."""
        columns, length = [[]], 0
        for group, size in zip(groups, sizes):
            if columns[-1] and length + size > most:
                columns.append([])
                length = 0
            columns[-1].append(group)
            length += size
        return columns

    most = max(sizes)
    while len(split(most)) > count:
        most += 1
    return split(most)
