# Various data structures in the gameta structures in the gameta structures in the game
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, ClassVar, Dict
import utils

farming_table = {}


# nft template_id
class NFT:
    Barley: int = 318606  # barley
    Corn: int = 318607  # corn
    Chicken: int = 298614  # Chicken
    Chick: int = 298613  # chick
    ChickenEgg: int = 298612  # egg
    BabyCalf: int = 298597  # Calf
    Calf: int = 298598  # calf
    FeMaleCalf: int = 298599  # Maiden
    MaleCalf: int = 298600  # Male cattle
    Bull: int = 298611  # bull
    DairyCow: int = 298607  # Cow
    CornSeed: int = 298596  # Corn seed
    BarleySeed: int = 298595  # Barley seed
    Milk: int = 298593  # milk


# Gold, wooden, food, energy
@dataclass(init=False)
class Resoure:
    energy: Decimal = None
    max_energy: Decimal = None
    gold: Decimal = None
    wood: Decimal = None
    food: Decimal = None


@dataclass(init=False)
class Token:
    fwg: Decimal = None
    fww: Decimal = None
    fwf: Decimal = None


@dataclass(init=False)
class MbsSavedClaims:
    Wood: int = 0
    Food: int = 0
    Gold: int = 0


# Operable crop
@dataclass(init=False)
class Farming:
    asset_id: str = None
    name: str = None
    template_id: int = None
    next_availability: datetime = None

    def show(self, more=True) -> str:
        if more:
            return f"[{self.name}] [{self.asset_id}] [Operating time:{utils.show_time(self.next_availability)}]"
        else:
            return f"[{self.name}] [{self.asset_id}]"


# ==== Food =====
# milk
@dataclass(init=False)
class Milk(Farming):
    name: str = "Milk"
    template_id: int = 298593


# corn
@dataclass(init=False)
class Corn(Farming):
    name: str = "Corn"
    template_id: int = 318607
    golds_cost: int = 82


# barley
@dataclass(init=False)
class Barley(Farming):
    name: str = "Barley"
    template_id: int = 318606
    golds_cost: int = 55


supported_foods = [Milk, Corn, Barley]
farming_table.update({cls.template_id: cls for cls in supported_foods})


# ==== Food =====

# ################### Animal ######################

# animal
@dataclass(init=False)
class Animal(Farming):
    # energy consumption
    energy_consumed: int = None
    # Current number of feeding
    times_claimed: int = None
    # Maximum number of feeding
    required_claims: int = None
    # Final feeding time
    last_claimed: datetime = None
    # Feeding time list
    day_claims_at: List[datetime] = None
    # interval
    charge_time: timedelta = None
    # 24-hour feeding
    daily_claim_limit: int = None
    # Consumed NFT
    consumed_card: int = None
    # Building
    required_building: int = None
    # Reproduction
    bearer_id: int = None
    partner_id: int = None

    def show(self, more=True, breeding=False) -> str:
        if more:
            if len(self.day_claims_at) >= self.daily_claim_limit:
                next_op_time = self.day_claims_at[0] + timedelta(hours=24)
                self.next_availability = max(self.next_availability, next_op_time)
            if not breeding:
                text = f"[{self.name}] [{self.asset_id}][24-hour feeding{len(self.day_claims_at)}/{self.daily_claim_limit}] [喂养次数{self.times_claimed}/{self.required_claims}] [可操作时间:{utils.show_time(self.next_availability)}] "
            else:
                text = f"[{self.name}Reproduction] [{self.bearer_id}][24-hour feeding{len(self.day_claims_at)}/{self.daily_claim_limit}] [喂养次数{self.times_claimed}/{self.required_claims}] [可操作时间:{utils.show_time(self.next_availability)}] "
            return text
        else:
            return f"[{self.name}] [{self.asset_id}]"


# Chicken
@dataclass(init=False)
class Chicken(Animal):
    name: str = "Chicken"
    template_id: int = 298614


# chick
@dataclass(init=False)
class Chick(Animal):
    name: str = "Chick"
    template_id: int = 298613


# chick
@dataclass(init=False)
class ChickenEgg(Animal):
    name: str = "ChickenEgg"
    template_id: int = 298612


# Calf
@dataclass(init=False)
class BabyCalf(Animal):
    name: str = "BabyCalf"
    template_id: int = 298597


# calf
@dataclass(init=False)
class Calf(Animal):
    name: str = "Calf"
    template_id: int = 298598


# Maiden
@dataclass(init=False)
class FeMaleCalf(Animal):
    name: str = "FeMaleCalf"
    template_id: int = 298599


# Male cattle
@dataclass(init=False)
class MaleCalf(Animal):
    name: str = "MaleCalf"
    template_id: int = 298600


# bull
@dataclass(init=False)
class Bull(Animal):
    name: str = "Bull"
    template_id: int = 298611


# Cow
@dataclass(init=False)
class DairyCow(Animal):
    name: str = "Dairy Cow"
    template_id: int = 298607


supported_animals = [Chicken, Chick, ChickenEgg, BabyCalf, Calf, FeMaleCalf, MaleCalf, DairyCow]

farming_table.update({cls.template_id: cls for cls in supported_animals})


def init_animal_config(rows: List[dict]):
    for item in rows:
        animal_class: Animal = farming_table.get(item["template_id"], None)
        if animal_class:
            animal_class.name = item["name"]
            animal_class.energy_consumed = item["energy_consumed"]
            animal_class.charge_time = timedelta(seconds=item["charge_time"])
            animal_class.required_claims = item["required_claims"]
            animal_class.daily_claim_limit = item["daily_claim_limit"]
            animal_class.consumed_card = item["consumed_card"]
            animal_class.required_building = item["required_building"]


# Animals - JSON data constructors returned from HTTP
def create_animal(item: dict, breeding=False) -> Animal:
    animal_class = farming_table.get(item["template_id"], None)
    if not animal_class:
        return None
    animal = animal_class()
    animal.day_claims_at = [datetime.fromtimestamp(item) for item in item["day_claims_at"]]
    animal.name = item["name"]
    animal.template_id = item["template_id"]
    animal.times_claimed = item.get("times_claimed", None)
    animal.last_claimed = datetime.fromtimestamp(item["last_claimed"])
    animal.next_availability = datetime.fromtimestamp(item["next_availability"])
    if not breeding:
        animal.asset_id = item["asset_id"]
    else:
        animal.required_claims = 9  #Breeding is only a cow, first write
        animal.daily_claim_limit = 3  # Breeding is only a cow, first write
        animal.consumed_card = 318607  # Breeding is only a cow, first write
        animal.bearer_id = item["bearer_id"]
        animal.partner_id = item["partner_id"]

    return animal


# Animals - JSON data constructors returned from HTTP
def create_breeding(item: dict) -> Animal:
    animal_class = farming_table.get(item["template_id"], None)
    if not animal_class:
        return None
    animal = animal_class()
    animal.day_claims_at = [datetime.fromtimestamp(item) for item in item["day_claims_at"]]
    animal.asset_id = item["asset_id"]
    animal.name = item["name"]
    animal.template_id = item["template_id"]
    animal.times_claimed = item.get("times_claimed", None)
    animal.last_claimed = datetime.fromtimestamp(item["last_claimed"])
    animal.next_availability = datetime.fromtimestamp(item["next_availability"])
    return animal


####################################################### Animal #######################################################

####################################################### Crop #######################################################

# Crop, barley, corn
@dataclass(init=False)
class Crop(Farming):
    times_claimed: int = None
    last_claimed: datetime = None

    # Maximum number of farming
    required_claims: int = None
    # energy consumption
    energy_consumed: int = None
    # Watering spacer
    charge_time: timedelta = None

    def show(self, more=True) -> str:
        if more:
            return f"[{self.name}] [{self.asset_id}] [Farming number{self.times_claimed}/{self.required_claims}] [Operating time:{utils.show_time(self.next_availability)}]"
        else:
            return f"[{self.name}] [{self.asset_id}]"


# Barley seed
@dataclass(init=False)
class BarleySeed(Crop):
    name: str = "Barley Seed"
    template_id: int = 298595
    golds_cost: int = 50


# Corn seed
@dataclass(init=False)
class CornSeed(Crop):
    name: str = "Corn Seed"
    template_id: int = 298596
    golds_cost: int = 75


supported_crops = [BarleySeed, CornSeed]

farming_table.update({cls.template_id: cls for cls in supported_crops})


def init_crop_config(rows: List[dict]):
    for item in rows:
        crop_class: Crop = farming_table.get(item["template_id"], None)
        if crop_class:
            crop_class.name = item["name"]
            crop_class.charge_time = timedelta(seconds=item["charge_time"])
            crop_class.energy_consumed = item["energy_consumed"]
            crop_class.required_claims = item["required_claims"]


# Constructing crop objects from JSON
def create_crop(item: dict) -> Crop:
    crop_class = farming_table.get(item["template_id"], None)
    if not crop_class:
        return None
    crop = crop_class()
    crop.asset_id = item["asset_id"]
    crop.name = item["name"]
    crop.times_claimed = item.get("times_claimed", None)
    crop.last_claimed = datetime.fromtimestamp(item["last_claimed"])
    crop.next_availability = datetime.fromtimestamp(item["next_availability"])
    return crop


####################################################### Tool #######################################################

# tool
@dataclass(init=False)
class Tool(Farming):
    # Current durable
    current_durability: Decimal = None
    # Maximum durable
    durability: Decimal = None

    # Output resource type
    mining_type: str = None
    # Minerality
    charge_time: timedelta = None
    # energy consumption
    energy_consumed: int = None
    # Durable consumption
    durability_consumed: int = None

    def show(self, more=True) -> str:
        if more:
            return f"[{self.name}] [{self.asset_id}] [Durability{self.current_durability}/{self.durability}] [Operating time:{utils.show_time(self.next_availability)}]"
        else:
            return f"[{self.name}] [{self.asset_id}]"


# ax
@dataclass(init=False)
class Axe(Tool):
    name: str = "Axe"
    template_id: int = 203881


# Stone bargain
@dataclass(init=False)
class StoneAxe(Tool):
    name: str = "Stone Axe"
    template_id: int = 260763


# Ancient stone
@dataclass(init=False)
class AncientStoneAxe(Tool):
    name: str = "Ancient Stone Axe"
    template_id: int = 378691


# Saw
@dataclass(init=False)
class Saw(Tool):
    name: str = "Saw"
    template_id: int = 203883


# Chainsaw
@dataclass(init=False)
class Chainsaw(Tool):
    name: str = "Chainsaw"
    template_id: int = 203886


# Fishing rod
@dataclass(init=False)
class FishingRod(Tool):
    name: str = "Fishing Rod"
    template_id: int = 203887


# Fish net
@dataclass(init=False)
class FishingNet(Tool):
    name: str = "Fishing Net"
    template_id: int = 203888


# Fishing boat
@dataclass(init=False)
class FishingBoat(Tool):
    name: str = "Fishing Boat"
    template_id: int = 203889


# excavator
@dataclass(init=False)
class MiningExcavator(Tool):
    name: str = "Mining Excavator"
    template_id: int = 203891


supported_tools = [Axe, StoneAxe, AncientStoneAxe, Saw, Chainsaw, FishingRod, FishingNet, FishingBoat, MiningExcavator]

farming_table.update({cls.template_id: cls for cls in supported_tools})


def init_tool_config(rows: List[dict]):
    for item in rows:
        tool_class = farming_table.get(item["template_id"], None)
        if tool_class:
            tool_class.mining_type = item["type"]
            tool_class.charge_time = timedelta(seconds=item["charged_time"])
            tool_class.energy_consumed = item["energy_consumed"]
            tool_class.durability_consumed = item["durability_consumed"]


# Tool object from JSON
def create_tool(item: dict) -> Tool:
    tool_class = farming_table.get(item["template_id"], None)
    if not tool_class:
        return None
    tool = tool_class()
    tool.asset_id = item["asset_id"]
    tool.next_availability = datetime.fromtimestamp(item["next_availability"])
    tool.current_durability = item["current_durability"]
    tool.durability = item["durability"]
    return tool


####################################################### Tool #######################################################

####################################################### MBS  #######################################################

# membership card
@dataclass(init=False)
class MBS(Farming):
    energy_consumed: int = 100

    def __init__(self, template_id, name, type, saved_claims):
        self.name = name
        self.template_id = template_id
        self.type = type
        self.saved_claims = saved_claims

    def show(self, more=True) -> str:
        if more:
            return f"[{self.name}] [type:{self.type}] [asset_id:{self.asset_id}] [Operating time:{utils.show_time(self.next_availability)}]"
        else:
            return f"[{self.name}] [type:{self.type}]"


mbs_table: Dict[int, MBS] = {}


def init_mbs_config(rows: List[dict]):
    for item in rows:
        mbs = MBS(item["template_id"], item["name"], item["type"], item["saved_claims"])
        mbs_table[item["template_id"]] = mbs


# Construct MBS object from JSON
def create_mbs(item: dict) -> MBS:
    mbs_class = mbs_table.get(item["template_id"], None)
    if not mbs_class:
        return None
    mbs = MBS(mbs_class.template_id, mbs_class.name, mbs_class.type, mbs_class.saved_claims)
    mbs.asset_id = item["asset_id"]
    mbs.next_availability = datetime.fromtimestamp(item["next_availability"])
    return mbs


####################################################### MBS #######################################################


# building
@dataclass(init=False)
class Building(Farming):
    # Energy consumption of cowshed 300, chicken house 250, field 200
    energy_consumed: int = 300
    times_claimed: int = None
    last_claimed: datetime = None
    is_ready: int = None
    slots_used: int = None
    num_slots: int = None


# NFT assets, can be wheat, wheat seeds, milk, etc.
@dataclass(init=False)
class Asset:
    asset_id: str
    name: str
    is_transferable: bool
    is_burnable: bool
    schema_name: str
    template_id: str
