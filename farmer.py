#!/usr/bin/python3
import random
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import WebDriverException
import shutil
import tenacity
from tenacity import stop_after_attempt, wait_fixed, retry_if_exception_type, RetryCallState
import logging
import requests
from requests.exceptions import RequestException
import functools
from decimal import Decimal
from typing import List, Dict
import base64
from pprint import pprint
import logger
import utils
from utils import plat
from settings import user_param
import res
from res import Building, Resoure, Animal, Asset, Farming, Crop, NFT, Axe, Tool, Token, Chicken, FishingRod, MBS
from res import BabyCalf, Calf, FeMaleCalf, MaleCalf, Bull, DairyCow, MbsSavedClaims

from datetime import datetime, timedelta
from settings import cfg
import os
from logger import log


class FarmerException(Exception):
    pass


class CookieExpireException(FarmerException):
    pass


# Call the intelligent contract error, should stop and check the log, should not repeated retry
class TransactException(FarmerException):
    # Some intelligent contract errors can retry, -1 is unlimited retry
    def __init__(self, msg, retry=True, max_retry_times: int = -1):
        super().__init__(msg)
        self.retry = retry
        self.max_retry_times = max_retry_times


# Negative incorrect mistakes, terminate the program
class StopException(FarmerException):
    pass


class Status:
    Continue = 1
    Stop = 2


class Farmer:
    # wax rpc
    # url_rpc = "https://api.wax.alohaeos.com/v1/chain/"
    # url_rpc = "https://wax.dapplica.io/v1/chain/"
    # url_table_row = url_rpc + "get_table_rows"
    # asset API
    # url_assets = "https://wax.api.atomicassets.io/atomicassets/v1/assets"
    # url_assets = "https://atomic.wax.eosrio.io/atomicassets/v1/assets"
    waxjs: str = None
    myjs: str = None
    chrome_data_dir = os.path.abspath(cfg.chrome_data_dir)

    def __init__(self):
        self.url_rpc: str = None
        self.url_table_row: str = None
        self.url_assets: str = None

        self.wax_account: str = None
        self.login_name: str = None
        self.password: str = None
        self.driver: webdriver.Chrome = None
        self.proxy: str = None
        self.http: requests.Session = None
        self.cookies: List[dict] = None
        self.log: logging.LoggerAdapter = log
        # The next time you can do something
        self.next_operate_time: datetime = datetime.max
        # Next scan time
        self.next_scan_time: datetime = datetime.min
        # Stateless things in this wheel scan
        self.not_operational: List[Farming] = []
        # Intelligent contract continuous error
        self.count_error_transact = 0
        # Successful number of crop operation in this wheel scan
        self.count_success_claim = 0
        # Number of crop operation failed in this wheel scan
        self.count_error_claim = 0
        # The number of resources at the beginning of this wheel
        self.resoure: Resoure = None
        self.token: Token = None
        self.mbs_saved_claims: MbsSavedClaims = None

    def close(self):
        if self.driver:
            self.log.info("Slightly, the program is exiting")
            self.driver.quit()

    def init(self):
        self.url_rpc = user_param.rpc_domain + '/v1/chain/'
        self.url_table_row = user_param.rpc_domain + '/v1/chain/get_table_rows'
        self.url_assets = user_param.assets_domain + '/atomicassets/v1/assets'

        self.log.extra["tag"] = self.wax_account
        options = webdriver.ChromeOptions()
        # options.add_argument("--headless")
        # options.add_argument("--no-sandbox")
        options.add_argument("--disable-extensions")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-logging")
        options.add_experimental_option('useAutomationExtension', False)
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        data_dir = os.path.join(Farmer.chrome_data_dir, self.wax_account)
        options.add_argument("--user-data-dir={0}".format(data_dir))
        if self.proxy:
            options.add_argument("--proxy-server={0}".format(self.proxy))
        # options.binary_location = shutil.which("brave-browse")
   
        self.driver = webdriver.Chrome(service=Service(plat.driver_path), options=options)
        self.driver.implicitly_wait(60)
        self.driver.set_script_timeout(60)
        self.http = requests.Session()
        self.http.trust_env = False
        self.http.request = functools.partial(self.http.request, timeout=30)
        if self.proxy:
            self.http.proxies = {
                "http": "http://{0}".format(self.proxy),
                "https": "http://{0}".format(self.proxy),
            }
        http_retry_wrapper = tenacity.retry(wait=wait_fixed(cfg.req_interval), stop=stop_after_attempt(5),
                                            retry=retry_if_exception_type(RequestException),
                                            before_sleep=self.log_retry, reraise=True)
        self.http.get = http_retry_wrapper(self.http.get)
        self.http.post = http_retry_wrapper(self.http.post)

    def inject_waxjs(self):
        # If you have injected over, you will no longer be injected.
        if self.driver.execute_script("return window.mywax != undefined;"):
            return True

        if not Farmer.waxjs:
            with open("waxjs.js", "r") as file:
                Farmer.waxjs = file.read()
                file.close()
                Farmer.waxjs = base64.b64encode(Farmer.waxjs.encode()).decode()
        if not Farmer.myjs:
            with open("inject.js", "r") as file:
                inject_rpc = "window.mywax = new waxjs.WaxJS({rpcEndpoint: '" + user_param.rpc_domain + "'});"
                Farmer.myjs = inject_rpc + file.read()
                file.close()

        code = "var s = document.createElement('script');"
        code += "s.type = 'text/javascript';"
        code += "s.text = atob('{0}');".format(Farmer.waxjs)
        code += "document.head.appendChild(s);"
        self.driver.execute_script(code)
        self.driver.execute_script(Farmer.myjs)
        return True

    def start(self):
        self.log.info("Start browser")
        self.log.info("WAX line point: {0}".format(user_param.rpc_domain))
        self.log.info("Atomic market node: {0}".format(user_param.assets_domain))
        if self.cookies:
            self.log.info("Automatically log in with preset cookies")
            cookies = self.cookies["cookies"]
            key_cookie = {}
            for item in cookies:
                if item.get("domain") == "all-access.wax.io":
                    key_cookie = item
                    break
            if not key_cookie:
                raise CookieExpireException("not find cookie domain as all-access.wax.io")
            ret = self.driver.execute_cdp_cmd("Network.setCookie", key_cookie)
            self.log.info("Network.setCookie: {0}".format(ret))
            if not ret["success"]:
                raise CookieExpireException("Network.setCookie error")
        self.driver.get("https://play.farmersworld.io/")
        # Waiting for the page to load
        elem = self.driver.find_element(By.ID, "RPC-Endpoint")
        elem.find_element(By.XPATH, "option[contains(@name, 'https')]")
        wait_seconds = 60
        if self.may_cache_login():
            self.log.info("Automatically log in with cache")
        else:
            wait_seconds = 600
            self.log.info("Please log in to the account in the pop-up window.")
        # Click the login button, click on Wax Cloud Workclic Mode to log in.
        elem = self.driver.find_element(By.CLASS_NAME, "login-button")
        elem.click()
        elem = self.driver.find_element(By.CLASS_NAME, "login-button--text")
        elem.click()
        # Waiting for login success
        self.log.info("Waiting for login")
        WebDriverWait(self.driver, wait_seconds, 1).until(
            EC.presence_of_element_located((By.XPATH, "//img[@class='navbar-group--icon' and @alt='Map']")))
        # self.driver.find_element(By.XPATH, "//img[@class='navbar-group--icon' and @alt='Map']")
        self.log.info("Successful login, wait a moment...")
        time.sleep(cfg.req_interval)
        self.inject_waxjs()
        ret = self.driver.execute_script("return window.wax_login();")
        self.log.info("window.wax_login(): {0}".format(ret))
        if not ret[0]:
            raise CookieExpireException("cookieFail")

        # Game parameters from the server
        self.log.info("Loading game configuration")
        self.init_farming_config()
        time.sleep(cfg.req_interval)

    def may_cache_login(self):
        cookies = self.driver.execute_cdp_cmd("Network.getCookies", {"urls": ["https://all-access.wax.io"]})
        for item in cookies["cookies"]:
            if item.get("name") == "token_id":
                return True
        return False

    def log_retry(self, state: RetryCallState):
        exp = state.outcome.exception()
        if isinstance(exp, RequestException):
            self.log.info("Network Error: {0}".format(exp))
            self.log.info("Try again: [{0}]".format(state.attempt_number))

    def get_table_row(self, post_data):
        resp = self.http_post(user_param.query_rpc_domain, '/v1/chain/get_table_rows', post_data)
        return resp

    def http_post(self, domain, api, post_data):
        # rpc_domain = random.choice(user_param.rpc_domain_list)
        url = domain + api
        resp = self.http.post(url, json=post_data)
        return resp

    def table_row_template(self) -> dict:
        post_data = {
            "json": True,
            "code": "farmersworld",
            "scope": "farmersworld",
            "table": None,  # Overwrite
            "lower_bound": self.wax_account,
            "upper_bound": self.wax_account,
            "index_position": None,  # Overwrite
            "key_type": "i64",
            "limit": 100,
            "reverse": False,
            "show_payer": False
        }
        return post_data

    # Get parameters of various tools and crops from the server
    def init_farming_config(self):
        # tool
        post_data = {
            "json": True,
            "code": "farmersworld",
            "scope": "farmersworld",
            "table": "toolconfs",
            "lower_bound": "",
            "upper_bound": "",
            "index_position": 1,
            "key_type": "",
            "limit": 100,
            "reverse": False,
            "show_payer": False
        }
        resp = self.get_table_row(post_data)
        self.log.debug("get tools config: {0}".format(resp.text))
        resp = resp.json()
        res.init_tool_config(resp["rows"])
        time.sleep(cfg.req_interval)

        # crop
        post_data["table"] = "cropconf"
        resp = self.get_table_row(post_data)
        self.log.debug("get crop config: {0}".format(resp.text))
        resp = resp.json()
        res.init_crop_config(resp["rows"])

        # animal
        post_data["table"] = "anmconf"
        resp = self.get_table_row(post_data)
        self.log.debug("get animal conf: {0}".format(resp.text))
        resp = resp.json()
        res.init_animal_config(resp["rows"])

        # membership card
        post_data["table"] = "mbsconf"
        resp = self.get_table_row(post_data)
        self.log.debug("get mbs config: {0}".format(resp.text))
        resp = resp.json()
        res.init_mbs_config(resp["rows"])

    # Get the configuration from the server
    def get_farming_config(self):
        post_data = {
            "json": True,
            "code": "farmersworld",
            "scope": "farmersworld",
            "table": "config",
            "lower_bound": "",
            "upper_bound": "",
            "index_position": 1,
            "key_type": "",
            "limit": 1,
            "reverse": False,
            "show_payer": False
        }
        resp = self.get_table_row(post_data)
        self.log.debug("get farming config: {0}".format(resp.text))
        resp = resp.json()

        return resp["rows"][0]

    # Get the number of three resources in the game and energy values
    def get_resource(self) -> Resoure:
        post_data = self.table_row_template()
        post_data["table"] = "accounts"
        post_data["index_position"] = 1

        resp = self.get_table_row(post_data)
        self.log.debug("get_table_rows:{0}".format(resp.text))
        resp = resp.json()
        if len(resp["rows"]) == 0:
            self.log.info("===============================")
            self.log.info("Get the account data, please check if the account name is incorrect")
            self.log.info("===============================")
        resource = Resoure()
        resource.energy = Decimal(resp["rows"][0]["energy"])
        resource.max_energy = Decimal(resp["rows"][0]["max_energy"])
        resource.gold = Decimal(0)
        resource.wood = Decimal(0)
        resource.food = Decimal(0)
        balances: List[str] = resp["rows"][0]["balances"]
        for item in balances:
            sp = item.split(" ")
            if sp[1].upper() == "GOLD":
                resource.gold = Decimal(sp[0])
            elif sp[1].upper() == "WOOD":
                resource.wood = Decimal(sp[0])
            elif sp[1].upper() == "FOOD":
                resource.food = Decimal(sp[0])
        self.log.debug("resource: {0}".format(resource))
        return resource

    # Get construction information
    def get_buildings(self) -> List[Building]:
        post_data = self.table_row_template()
        post_data["table"] = "buildings"
        post_data["index_position"] = 2

        resp = self.get_table_row(post_data)
        self.log.debug("get_buildings_info:{0}".format(resp.text))
        resp = resp.json()
        buildings = []
        for item in resp["rows"]:
            build = Building()
            build.asset_id = item["asset_id"]
            build.name = item["name"]
            build.is_ready = item["is_ready"]
            build.next_availability = datetime.fromtimestamp(item["next_availability"])
            build.template_id = item["template_id"]
            build.times_claimed = item.get("times_claimed", None)
            build.slots_used = item.get("slots_used", None)
            if build.is_ready == 1:
                continue
            buildings.append(build)
        return buildings

    # Get crop information
    def get_crops(self) -> List[Crop]:
        post_data = self.table_row_template()
        post_data["table"] = "crops"
        post_data["index_position"] = 2

        resp = self.get_table_row(post_data)
        self.log.debug("get_crops_info:{0}".format(resp.text))
        resp = resp.json()
        crops = []
        for item in resp["rows"]:
            crop = res.create_crop(item)
            if crop:
                crops.append(crop)
            else:
                self.log.warning("Crop type that has not yet been supported: {0}".format(item))
        return crops

    # claim 建筑
    def claim_building(self, item: Building):
        self.consume_energy(Decimal(item.energy_consumed))

        transaction = {
            "actions": [{
                "account": "farmersworld",
                "name": "bldclaim",
                "authorization": [{
                    "actor": self.wax_account,
                    "permission": "active",
                }],
                "data": {
                    "asset_id": item.asset_id,
                    "owner": self.wax_account,
                },
            }],
        }
        return self.wax_transact(transaction)

    # Cultivation crops
    def claim_crop(self, crop: Crop):
        energy_consumed = crop.energy_consumed
        fake_consumed = Decimal(0)
        if crop.times_claimed == crop.required_claims - 1:
            # The last farming before harvest, you need 200 energy, the game contract bug (corn needs 245)
            fake_consumed = Decimal(250)
        self.consume_energy(Decimal(energy_consumed), fake_consumed)
        transaction = {
            "actions": [{
                "account": "farmersworld",
                "name": "cropclaim",
                "authorization": [{
                    "actor": self.wax_account,
                    "permission": "active",
                }],
                "data": {
                    "crop_id": crop.asset_id,
                    "owner": self.wax_account,
                },
            }],
        }
        return self.wax_transact(transaction)

    def claim_buildings(self, blds: List[Building]):
        for item in blds:
            self.log.info("Be constructed: {0}".format(item.show()))
            if self.claim_building(item):
                self.log.info("Successful: {0}".format(item.show(more=False)))
            else:
                self.log.info("Construction failure: {0}".format(item.show(more=False)))
                self.count_error_claim += 1
            time.sleep(cfg.req_interval)

    def claim_crops(self, crops: List[Crop]):
        for item in crops:
            self.log.info("Regular cultivation: {0}".format(item.show()))
            if self.claim_crop(item):
                self.log.info("Tillage success: {0}".format(item.show(more=False)))
            else:
                self.log.info("Farming failure: {0}".format(item.show(more=False)))
                self.count_error_claim += 1
            time.sleep(cfg.req_interval)

    # Get NTF in the box
    def get_chest(self) -> dict:
        payload = {
            "limit": 1000,
            "collection_name": "farmersworld",
            "owner": self.wax_account,
            "template_blacklist": "260676",
        }
        resp = self.http.get(self.url_assets, params=payload)
        self.log.debug("get_chest:{0}".format(resp.text))
        resp = resp.json()
        assert resp["success"]
        return resp

    # schema: [foods]
    def get_chest_by_schema_name(self, schema_name: str):
        payload = {
            "limit": 1000,
            "collection_name": "farmersworld",
            "owner": self.wax_account,
            "schema_name": schema_name,
        }
        resp = self.http.get(self.url_assets, params=payload)
        self.log.debug("get_chest_by_schema_name: {0}".format(resp.text))
        resp = resp.json()
        assert resp["success"]
        return resp

    # template_id: [barley 318606] [corn 318607]
    def get_chest_by_template_id(self, template_id: int):
        payload = {
            "limit": 1000,
            "collection_name": "farmersworld",
            "owner": self.wax_account,
            "template_id": template_id,
        }
        resp = self.http.get(self.url_assets, params=payload)
        self.log.debug("get_chest_by_template_id: {0}".format(resp.text))
        resp = resp.json()
        assert resp["success"]
        return resp

    # Get barley
    def get_barley(self) -> List[Asset]:
        barley_list = self.get_asset(NFT.Barley, 'Barley')
        return barley_list

    # Get milk
    def get_milk(self) -> List[Asset]:
        milk_list = self.get_asset(NFT.Milk, 'Milk')
        return milk_list

    # Get eggs
    def get_egg(self) -> List[Asset]:
        egg_list = self.get_asset(NFT.ChickenEgg, 'ChickenEgg')
        return egg_list

    # Get corn
    def get_corn(self) -> List[Asset]:
        corn_list = self.get_asset(NFT.Corn, 'Corn')
        return corn_list

    # Get NFT assets, can be wheat, wheat seeds, milk, etc.
    def get_asset(self, template_id, name) -> List[Asset]:
        asset_list = []
        chest = self.get_chest_by_template_id(template_id)
        if len(chest["data"]) <= 0:
            return asset_list
        for item in chest["data"]:
            asset = Asset()
            asset.asset_id = item["asset_id"]
            asset.name = item["name"]
            asset.is_transferable = item["is_transferable"]
            asset.is_burnable = item["is_transferable"]
            asset.schema_name = item["schema"]["schema_name"]
            asset.template_id = item["template"]["template_id"]
            asset_list.append(asset)
        self.log.debug("[{0}]_get_asset_list: [{1}]".format(name, format(asset_list)))
        return asset_list

    # Get information of animals
    def get_breedings(self) -> List[Animal]:
        post_data = self.table_row_template()
        post_data["table"] = "breedings"
        post_data["index_position"] = 2

        resp = self.get_table_row(post_data)
        self.log.debug("get_breedings:{0}".format(resp.text))
        resp = resp.json()
        if len(resp["rows"]) == 0:
            self.log.warning("No animals that are breeding, please open the breeding first.")
        animals = []
        for item in resp["rows"]:
            anim = res.create_animal(item, True)
            if anim:
                animals.append(anim)
            else:
                self.log.info("Animals that have not yet been supported")
        return animals

    def get_animals(self) -> List[Animal]:
        post_data = self.table_row_template()
        post_data["table"] = "animals"
        post_data["index_position"] = 2

        resp = self.get_table_row(post_data)
        self.log.debug("get_animal_info: {0}".format(resp.text))
        resp = resp.json()
        if len(resp["rows"]) == 0:
            self.log.warning("No animals in the account")
        animals = []
        for item in resp["rows"]:
            anim = res.create_animal(item)
            if anim:
                if anim.required_building == 298590 and user_param.cow:
                    # Cowshed
                    animals.append(anim)
                elif anim.required_building == 298591 and user_param.chicken:
                    # Chicken house
                    animals.append(anim)
            else:
                self.log.info("Animals not yet supported: {0}".format(item["name"]))

        return animals

    # Feeding animals
    def feed_animal(self, asset_id_food: str, animal: Animal, breeding=False) -> bool:

        fake_consumed = Decimal(0)
        if animal.times_claimed == animal.required_claims - 1:
            # The last feeding before harvest, 200 points, the game contract bug
            fake_consumed = Decimal(200)
        self.consume_energy(Decimal(animal.energy_consumed), fake_consumed)
        if not breeding:
            self.log.info("feed [{0}] to [{1}]".format(asset_id_food, animal.asset_id))
            memo = "feed_animal: {0}".format(animal.asset_id)
        else:
            self.log.info("feed [{0}] to [{1}]".format(asset_id_food, animal.bearer_id))
            memo = "breed_animal: {0},{1}".format(animal.bearer_id, animal.partner_id)

        transaction = {
            "actions": [{
                "account": "atomicassets",
                "name": "transfer",
                "authorization": [{
                    "actor": self.wax_account,
                    "permission": "active",
                }],
                "data": {
                    "asset_ids": [asset_id_food],
                    "from": self.wax_account,
                    "memo": memo,
                    "to": "farmersworld"
                },
            }],
        }
        return self.wax_transact(transaction)

    #  Get food needed by animals
    def get_animal_food(self, animal: Animal):
        food_class = res.farming_table.get(animal.consumed_card)
        list_food = self.get_asset(animal.consumed_card, food_class.name)
        self.log.info("Remainder [{0}] quantity: [{1}]".format(food_class.name, len(list_food)))
        if len(list_food) <= 0:
            rs = self.buy_corps(animal.consumed_card, user_param.buy_food_num)
            if not rs:
                self.log.warning("{0}Insufficient quantity, please supplement in time".format(food_class.name))
                return False
            else:
                list_food = self.get_asset(animal.consumed_card, food_class.name)
        asset = list_food.pop()

        return asset.asset_id

    # Feeding animal
    def claim_animal(self, animals: List[Animal]):
        for item in animals:
            self.log.info("Feeding [{0}]: [{1}]".format(item.name, item.show()))
            if 'Egg' in item.name:
                success = self.care_animal(item)
            else:
                feed_asset_id = self.get_animal_food(item)
                if not feed_asset_id:
                    return False
                success = self.feed_animal(feed_asset_id, item)

            if success:
                self.log.info("Successful: {0}".format(item.show(more=False)))
            else:
                self.log.info("Feeding failure: {0}".format(item.show(more=False)))
                self.count_error_claim += 1
            time.sleep(cfg.req_interval)
        return True

    # Breeding reproduced animal
    def breeding_claim(self, animals: List[Animal]):

        for item in animals:
            self.log.info("[Breeding] is being fed[{0}]: [{1}]".format(item.name, item.show(False, True)))
            feed_asset_id = self.get_animal_food(item)
            if not feed_asset_id:
                return False
            success = self.feed_animal(feed_asset_id, item, True)

            if success:
                self.log.info("[Breeding] feeding success: {0}".format(item.show(more=False, breeding=True)))
            else:
                self.log.info("[Breeding] feeding failure: {0}".format(item.show(more=False, breeding=True)))
                self.count_error_claim += 1
            time.sleep(cfg.req_interval)
        return True

    def care_animal(self, animal: Animal):
        self.log.info("care_animal {0}".format(animal.asset_id))
        fake_consumed = Decimal(0)
        if animal.times_claimed == animal.required_claims - 1:
            # The last feeding before harvest, 200 points, the game contract bug
            fake_consumed = Decimal(200)
        self.consume_energy(Decimal(animal.energy_consumed), fake_consumed)

        transaction = {
            "actions": [{
                "account": "farmersworld",
                "name": "anmclaim",
                "authorization": [{
                    "actor": self.wax_account,
                    "permission": "active",
                }],
                "data": {
                    "animal_id": animal.asset_id,
                    "owner": self.wax_account,
                },
            }],
        }
        return self.wax_transact(transaction)

    # Get WAX Account Information
    def wax_get_account(self):
        post_data = {"account_name": self.wax_account}
        resp = self.http_post(user_param.query_rpc_domain, '/v1/chain/get_account', post_data)
        self.log.debug("get_account:{0}".format(resp.text))
        resp = resp.json()
        return resp

    # Get the balance of the three resources FWF FWG FWW
    def get_fw_balance(self) -> Token:
        post_data = {
            "code": "farmerstoken",
            "account": self.wax_account,
            "symbol": None
        }
        resp = self.http_post(user_param.query_rpc_domain, '/v1/chain/get_currency_balance', post_data)

        self.log.debug("get_fw_balance:{0}".format(resp.text))
        resp = resp.json()
        balance = Token()
        balance.fwf = 0
        balance.fwg = 0
        balance.fww = 0
        for item in resp:
            sp = item.split(" ")
            if sp[1].upper() == "FWF":
                balance.fwf = Decimal(sp[0])
            elif sp[1].upper() == "FWG":
                balance.fwg = Decimal(sp[0])
            elif sp[1].upper() == "FWW":
                balance.fww = Decimal(sp[0])
        self.log.debug("fw_balance: {0}".format(balance))
        return balance

    # Sign the transaction (only a success, otherwise throwing it)
    def wax_transact(self, transaction: dict):
        self.inject_waxjs()
        self.log.info("begin transact: {0}".format(transaction))
        try:
            success, result = self.driver.execute_script("return window.wax_transact(arguments[0]);", transaction)
            if success:
                self.log.info("transact ok, transaction_id: [{0}]".format(result["transaction_id"]))
                self.log.debug("transact result: {0}".format(result))
                time.sleep(cfg.transact_interval)
                return result
            else:
                if "is greater than the maximum billable" in result:
                    self.log.error("CPUInsufficient resources, may need to pledge more Wax, generally false, retry latermaximum")
                elif "estimated CPU time (0 us) is not less than the maximum billable CPU time for the transaction (0 us)" in result:
                    self.log.error("CPUInsufficient resources, may need to pledge more Wax, generally false, retry later estimated")
                else:
                    self.log.error("transact error: {0}".format(result))
                raise TransactException(result)

        except WebDriverException as e:
            self.log.error("transact error: {0}".format(e))
            self.log.exception(str(e))
            raise TransactException(result)

    # Filtration of operable crops
    def filter_operable(self, items: List[Farming]) -> Farming:
        now = datetime.now()
        op = []
        for item in items:
            if isinstance(item, Building):
                if item.is_ready == 1:
                    continue
            # daily_claim_limit:
            # Chickens should be fed up to 4 times in 24 hours
            # Feed cows up to 6 times in 24 hours
            # Calves should be fed up to 2 times in 24 hours
            if isinstance(item, Animal):
                if len(item.day_claims_at) >= item.daily_claim_limit:
                    next_op_time = item.day_claims_at[0] + timedelta(hours=24)
                    item.next_availability = max(item.next_availability, next_op_time)
                    self.log.info("[{0}] feed [{1}] times in 24 hours.".format(item.name, item.daily_claim_limit))
            if now < item.next_availability:
                self.not_operational.append(item)
                continue
            op.append(item)

        return op

    def scan_buildings(self):
        self.log.info("Check the buildings")
        buildings = self.get_buildings()
        if not buildings:
            self.log.info("No unfinished buildings")
            return True
        self.log.info("Unfinished buildings:")
        for item in buildings:
            self.log.info(item.show())
        buildings = self.filter_operable(buildings)
        if not buildings:
            self.log.info("There is no operational building")
            return True
        self.log.info("Own building:")
        for item in buildings:
            self.log.info(item.show())
        self.claim_buildings(buildings)
        return True

    def scan_plants(self):
        self.log.info("Automatic farming")
        post_data = self.table_row_template()
        post_data["table"] = "buildings"
        post_data["index_position"] = 2

        resp = self.get_table_row(post_data)
        self.log.debug("get_buildings_info: {0}".format(resp.text))
        resp = resp.json()
        for item in resp["rows"]:
            if item["template_id"] == 298592 and item["is_ready"] == 1:
                slots_num = 8 - item["slots_used"]
                if slots_num > 0:
                    self.plant_corps(slots_num)
                else:
                    self.log.info("No unused plot")
        return True

    # Purchase crop
    def buy_corps(self, template_id: int, buy_num: int):
        if buy_num <= 0:
            self.log.info("The number of purchases is 0")
            return False
        item_class = res.farming_table.get(template_id)
        total_golds = item_class.golds_cost * buy_num
        if total_golds > self.resoure.gold:
            new_buy_num = int(self.resoure.gold / item_class.golds_cost)
            if new_buy_num <= 0:
                self.log.info("Insufficient gold coins to buy, please replenish gold coins first.")
                return False
            else:
                self.log.info("Insufficient gold coins. You need [{0}], only [{1}] available".format(buy_num, new_buy_num))
                buy_num = new_buy_num

        if user_param.buy_barley_seed and template_id == 298595:
            self.log.info("Start buying barley seeds, quantity：{0}".format(buy_num))
            self.market_buy(template_id, buy_num)
        elif user_param.buy_corn_seed and template_id == 298596:
            self.log.info("Start buying corn seeds, quantity：{0}".format(buy_num))
            self.market_buy(template_id, buy_num)
        elif user_param.buy_food and template_id == 318606:
            self.log.info("Start buy barley, quantity：{0}".format(buy_num))
            self.market_buy(template_id, buy_num)
        elif user_param.buy_food and template_id == 318607:
            self.log.info("Start buying corn, quantity：{0}".format(buy_num))
            self.market_buy(template_id, buy_num)
        else:
            self.log.info("The purchase of this type of resource is disabled in the settings")

        time.sleep(2)
        return True

    # Market purchase
    def market_buy(self, template_id: int, buy_num: int):

        transaction = {
            "actions": [{
                "account": "farmersworld",
                "name": "mktbuy",
                "authorization": [{
                    "actor": self.wax_account,
                    "permission": "active",
                }],
                "data": {
                    "owner": self.wax_account,
                    "quantity": buy_num,
                    "template_id": template_id,
                },
            }],
        }
        self.wax_transact(transaction)
        self.log.info("Buy completed")

        return True

    # Plant
    def plant_corps(self, slots_num):
        self.log.info("Get barley or corn seeds")
        if user_param.barleyseed_num > 0:
            barleyseed_list = self.get_asset(298595, 'Barley Seed')
            plant_times = min(slots_num, user_param.barleyseed_num)
            if len(barleyseed_list) < plant_times and user_param.buy_barley_seed:
                self.log.warning("Insufficient quantity of barley seeds, starting the market purchase")
                buy_barleyseed_num = plant_times - len(barleyseed_list)
                rs = self.buy_corps(298595, buy_barleyseed_num)
                if not rs:
                    return False
                else:
                    barleyseed_list = self.get_asset(298595, 'Barley Seed')
            if len(barleyseed_list) > 0:
                for i in range(plant_times):
                    asset = barleyseed_list.pop()
                    self.wear_assets([asset.asset_id])
            else:
                self.log.info("Insufficient quantity of barley seeds, please supplement in time")
        else:
            self.log.info("The amount of barley seeds is 0")

        if user_param.cornseed_num > 0:
            cornseed_list = self.get_asset(298596, 'Corn Seed')
            plant_times2 = min(slots_num, user_param.cornseed_num)
            if len(cornseed_list) < plant_times2 and user_param.buy_corn_seed:
                self.log.warning("Insufficient quantity of corn seeds, starting market purchase")
                buy_cornseed_num = plant_times2 - len(cornseed_list)
                rs = self.buy_corps(298596, buy_cornseed_num)
                if not rs:
                    return False
                else:
                    cornseed_list = self.get_asset(298596, 'Corn Seed')
            if len(cornseed_list) > 0:
                for i in range(plant_times2):
                    asset = cornseed_list.pop()
                    self.wear_assets([asset.asset_id])
            else:
                self.log.info("Insufficient quantity of corn seeds, please supplement in time")
        else:
            self.log.info("The amount of corn seeds is 0")

        return True

    # Wearing tools, departments - (farm: corn, wheat)
    def wear_assets(self, asset_ids):
        self.log.info("Seeding [Corn seed | Barley seed]")
        transaction = {
            "actions": [{
                "account": "atomicassets",
                "name": "transfer",
                "authorization": [{
                    "actor": self.wax_account,
                    "permission": "active",
                }],
                "data": {
                    "from": self.wax_account,
                    "to": "farmersworld",
                    "asset_ids": asset_ids,
                    "memo": "stake",
                },
            }],
        }
        self.wax_transact(transaction)
        self.log.info("Seeding completed")
        time.sleep(cfg.req_interval)

    def scan_crops(self):
        self.log.info("Inspecting farmland")
        crops = self.get_crops()
        if not crops:
            self.log.info("No crop")
            return True
        self.log.info("Planting crops:")
        for item in crops:
            self.log.info(item.show())
        crops = self.filter_operable(crops)
        if not crops:
            self.log.info("There is no operable crop")
            return True
        self.log.info("Operable crops:")
        for item in crops:
            self.log.info(item.show())
        self.claim_crops(crops)
        return True

    # Sale of corn and barley
    def scan_nft_assets(self):
        asset_ids = []
        sell_barley_num = 0
        sell_corn_num = 0
        sell_milk_num = 0
        sell_egg_num = 0
        if user_param.sell_corn:
            self.log.info("Check corn")
            list_corn = self.get_corn()
            self.log.info("The remaining corn: {0}".format(len(list_corn)))
            if len(list_corn) > 0:
                for item in list_corn:
                    if len(list_corn) - sell_corn_num <= user_param.remaining_corn_num:
                        break
                    asset_ids.append(item.asset_id)
                    sell_corn_num = sell_corn_num + 1

        if user_param.sell_barley:
            self.log.info("Check barley")
            list_barley = self.get_barley()
            self.log.info("The remaining barley: {0}".format(len(list_barley)))
            if len(list_barley) > 0:
                for item in list_barley:
                    if len(list_barley) - sell_barley_num <= user_param.remaining_barley_num:
                        break
                    asset_ids.append(item.asset_id)
                    sell_barley_num = sell_barley_num + 1
        if user_param.sell_milk:
            self.log.info("Check milk")
            list_milk = self.get_milk()
            self.log.info("The remaining milk: {0}".format(len(list_milk)))
            if len(list_milk) > 0:
                for item in list_milk:
                    if len(list_milk) - sell_milk_num <= user_param.remaining_milk_num:
                        break
                    asset_ids.append(item.asset_id)
                    sell_milk_num = sell_milk_num + 1

        if user_param.sell_egg:
            self.log.info("Check eggs")
            list_egg = self.get_egg()
            self.log.info("The remaining eggs: {0}".format(len(list_egg)))
            if len(list_egg) > 0:
                for item in list_egg:
                    if len(list_egg) - sell_egg_num <= user_param.remaining_egg_num:
                        break
                    asset_ids.append(item.asset_id)
                    sell_egg_num = sell_egg_num + 1

        if len(asset_ids) <= 0:
            self.log.warning("No NFT assets to sell [corn | wheat | milk | eggs]")
            return True

        self.burn_assets(asset_ids)
        self.log.warning(
            "Total sold quantity:[{0}], Corn [{1}], barley [{2}], milk [{3}], eggs [{4}]".format(len(asset_ids), sell_corn_num, sell_barley_num,
                                                                 sell_milk_num, sell_egg_num))
        return True

    # Sell assets - corn, wheat and milk
    def burn_assets(self, asset_ids):
        self.log.info("Selling assets [corn | wheat | milk | eggs]")
        transaction = {
            "actions": [{
                "account": "atomicassets",
                "name": "transfer",
                "authorization": [{
                    "actor": self.wax_account,
                    "permission": "active",
                }],
                "data": {
                    "from": self.wax_account,
                    "to": "farmersworld",
                    "asset_ids": asset_ids,
                    "memo": "burn",
                },
            }],
        }
        self.wax_transact(transaction)
        self.log.info("Sale has been completed")
        time.sleep(cfg.req_interval)

    def scan_breedings(self):
        self.log.info("Check the reproductive animal")
        breedings = self.get_breedings()
        self.log.info("Breeding reproduced animal:")
        for item in breedings:
            self.log.info(item.show())
        breedings = self.filter_operable(breedings)
        if not breedings:
            self.log.info("No animal")
            return True
        self.log.info("Operable breeding animals:")
        for item in breedings:
            self.log.info(item.show())
        self.breeding_claim(breedings)
        return True

    def scan_animals(self):
        self.log.info("Inspect animals")
        animals = self.get_animals()
        self.log.info("Raised animals:")
        for item in animals:
            self.log.info(item.show())
        animals = self.filter_operable(animals)
        if not animals:
            self.log.info("No operable animals")
            return True
        self.log.info("Operable animals:")
        for item in animals:
            self.log.info(item.show())
        self.claim_animal(animals)
        return True

    def get_tools(self):
        post_data = self.table_row_template()
        post_data["table"] = "tools"
        post_data["index_position"] = 2

        resp = self.get_table_row(post_data)
        self.log.debug("get_tools: {0}".format(resp.text))
        resp = resp.json()
        tools = []
        for item in resp["rows"]:
            tool = res.create_tool(item)
            if tool:
                tools.append(tool)
            else:
                self.log.warning("Tool types that have not yet been supported: {0}".format(item))
        return tools

    # Tool mining operation 1
    def claim_mining(self, tools: List[Tool]):
        enough_tools = []
        not_enough_tools = []
        for item in tools:
            check_status = self.check_durability(item)
            if check_status:
                enough_tools.append(item)
            else:
                not_enough_tools.append(item)
        # Durable enough
        self.do_mining(enough_tools)
        # Post-durable post-durability
        self.do_mining(not_enough_tools)

    # Tool mining operation 2
    def do_mining(self, tools: List[Tool]):
        for item in tools:
            self.log.info("Mining: {0}".format(item.show()))
            self.consume_energy(Decimal(item.energy_consumed))
            self.consume_durability(item)
            transaction = {
                "actions": [{
                    "account": "farmersworld",
                    "name": "claim",
                    "authorization": [{
                        "actor": self.wax_account,
                        "permission": "active",
                    }],
                    "data": {
                        "asset_id": item.asset_id,
                        "owner": self.wax_account,
                    },
                }],
            }
            self.wax_transact(transaction)
            # ming_resource = result["processed"]["action_traces"][0]["inline_traces"][1]["act"]["data"]["rewards"]
            # self.log.info("Mining success: {0},{1}".format(item.show(more=False), ming_resource))
            self.log.info("Mining success: {0}".format(item.show(more=False)))
            time.sleep(cfg.req_interval)

    def scan_mining(self):
        self.log.info("Check the mine")
        tools = self.get_tools()
        self.log.info("Mining tool:")
        if user_param.mbs and user_param.mbs_mint:
            self.log.info("Membership card storage mining has been enabled")
            
        for item in tools:
            if user_param.mbs and user_param.mbs_mint:
                if item.mining_type == 'Wood':
                    item.next_availability = item.next_availability + item.charge_time * self.mbs_saved_claims.Wood
                    item.energy_consumed = item.energy_consumed * (self.mbs_saved_claims.Wood+1)
                    item.durability_consumed = item.durability_consumed * (self.mbs_saved_claims.Wood+1)
                if item.mining_type == 'Food':
                    item.next_availability = item.next_availability + item.charge_time * self.mbs_saved_claims.Food
                    item.energy_consumed = item.energy_consumed * (self.mbs_saved_claims.Food + 1)
                    item.durability_consumed = item.durability_consumed * (self.mbs_saved_claims.Food + 1)
                if item.mining_type == 'Gold':
                    item.next_availability = item.next_availability + item.charge_time * self.mbs_saved_claims.Gold
                    item.energy_consumed = item.energy_consumed * (self.mbs_saved_claims.Gold + 1)
                    item.durability_consumed = item.durability_consumed * (self.mbs_saved_claims.Gold + 1)
            self.log.info(item.show())
        tools = self.filter_operable(tools)
        if not tools:
            self.log.info("No operable mining tool")
            return True
        self.log.info("Available mining tools:")
        for item in tools:
            self.log.info(item.show())
        self.claim_mining(tools)
        return True

    # Recharge
    def scan_deposit(self):
        self.log.info("Check if deposit is required")
        r = self.resoure

        deposit_wood = 0
        deposit_food = 0
        deposit_gold = 0

        if r.wood <= user_param.fww_min:
            deposit_wood = user_param.deposit_fww
            if 0 < self.token.fww < deposit_wood:
                deposit_wood = self.token.fww
                self.log.info(f"Insufficient FWW, the remaining {deposit_wood}FWW tokens will be fully deposited")
            elif self.token.fww == 0 and deposit_wood > 0:
                self.log.info(f"FWW is 0, please buy first {deposit_wood}FWW token")
                return False
        if r.gold <= user_param.fwg_min:
            deposit_gold = user_param.deposit_fwg
            if 0 < self.token.fwg < deposit_gold:
                deposit_gold = self.token.fwg
                self.log.info(f"Insufficient FWG, the remaining {deposit_gold}FWG tokens will be fully deposited")
            elif self.token.fwg == 0 and deposit_gold > 0:
                self.log.info(f"FWG is 0, please buy first {deposit_gold}FWG token")
                return False
        if r.food <= user_param.fwf_min:
            deposit_food = user_param.deposit_fwf
            if 0 < self.token.fwf < deposit_food:
                deposit_food = self.token.fwf
                self.log.info(f"Insufficient FWF, remaining {deposit_food}FWF tokens will be fully deposited")
            elif self.token.fwf == 0 and deposit_food > 0:
                self.log.info(f"FWF is 0, please buy first {deposit_food}FWF")
                return False
        if deposit_wood + deposit_food + deposit_gold == 0:
            self.log.info("The amount of deposit is 0, no need to deposit")
        else:
            self.do_deposit(deposit_food, deposit_gold, deposit_wood)
            self.log.info(f"Deposit: Gold[{deposit_gold}]  Wood[{deposit_wood}]  Food[{deposit_food}] ")

        return True

    # Recharge
    def do_deposit(self, food, gold, wood):
        self.log.info("Deposit")
        # format(1.23456, '.4f')
        quantities = []
        if food > 0:
            food = format(food, '.4f')
            quantities.append(food + " FWF")
        if gold > 0:
            gold = format(gold, '.4f')
            quantities.append(gold + " FWG")
        if wood > 0:
            wood = format(wood, '.4f')
            quantities.append(wood + " FWW")
        # quantities format: 1.0000 FWW
        transaction = {
            "actions": [{
                "account": "farmerstoken",
                "name": "transfers",
                "authorization": [{
                    "actor": self.wax_account,
                    "permission": "active",
                }],
                "data": {
                    "from": self.wax_account,
                    "to": "farmersworld",
                    "quantities": quantities,
                    "memo": "deposit",
                },
            }],
        }
        self.wax_transact(transaction)
        self.log.info("Deposit complete")

    # withdraw
    def do_withdraw(self, food, gold, wood, fee):
        self.log.info("Withdraw")
        # format(1.23456, '.4f')
        quantities = []
        if food > 0:
            food = format(food, '.4f')
            quantities.append(food + " FOOD")
        if gold > 0:
            gold = format(gold, '.4f')
            quantities.append(gold + " GOLD")
        if wood > 0:
            wood = format(wood, '.4f')
            quantities.append(wood + " WOOD")

        # Format: 1.0000 WOOD
        transaction = {
            "actions": [{
                "account": "farmersworld",
                "name": "withdraw",
                "authorization": [{
                    "actor": self.wax_account,
                    "permission": "active",
                }],
                "data": {
                    "owner": self.wax_account,
                    "quantities": quantities,
                    "fee": fee,
                },
            }],
        }
        self.wax_transact(transaction)
        self.log.info("Withdrawal complete")

    # Repair tool
    def repair_tool(self, tool: Tool):
        self.log.info(f"Repairing tool: {tool.show()}")
        consume_gold = (tool.durability - tool.current_durability) // 5
        if Decimal(consume_gold) > self.resoure.gold:
            raise FarmerException("There are not enough gold to repair tools, please replenish gold, the program will automatically retry later.")

        transaction = {
            "actions": [{
                "account": "farmersworld",
                "name": "repair",
                "authorization": [{
                    "actor": self.wax_account,
                    "permission": "active",
                }],
                "data": {
                    "asset_id": tool.asset_id,
                    "asset_owner": self.wax_account,
                },
            }],
        }
        self.wax_transact(transaction)
        self.log.info(f"Repaired: {tool.show(more=False)}")

    # Recovery energy
    def recover_energy(self, count: Decimal):
        self.log.info("Recovering energy: [{0}] point ".format(count))
        need_food = count // Decimal(5)
        if need_food > self.resoure.food:
            if self.resoure.food <= 0:
                # Insufficient food, open recharge
                if user_param.auto_deposit:
                    self.log.info("Insufficient food, trying to deposit")
                    self.scan_deposit()
                else:
                    self.log.info(f"Insufficient food, can't deposit, only [{self.resoure.food}] is left，and [{count}] points of energy are needed to exchange [{need_food}] food, please handle it manually")
                raise FarmerException("There is not enough food, please add food, the program will automatically retry later")
            else:
                count = self.resoure.food * Decimal(5)
                self.log.info(f"Food is insufficient, the remaining [{self.resoure.food}] food can add [{count}] points of energy")

        transaction = {
            "actions": [{
                "account": "farmersworld",
                "name": "recover",
                "authorization": [{
                    "actor": self.wax_account,
                    "permission": "active",
                }],
                "data": {
                    "energy_recovered": int(count),
                    "owner": self.wax_account,
                },
            }],
        }
        return self.wax_transact(transaction)

    # Consumption (Pre-operation simulation)
    def consume_energy(self, real_consume: Decimal, fake_consume: Decimal = Decimal(0)):
        consume = real_consume + fake_consume
        if self.resoure.energy - consume >= 0:
            self.resoure.energy -= real_consume
            return True
        else:
            self.log.info("Insufficient energy")
            recover = min(user_param.recover_energy, self.resoure.max_energy) - self.resoure.energy
            recover = (recover // Decimal(5)) * Decimal(5)
            self.recover_energy(recover)
            self.resoure.energy += recover
            self.resoure.energy -= real_consume
            return True

    # Consuming durability (before operation, simulation)
    def consume_durability(self, tool: Tool):
        check_status = self.check_durability(tool)
        if check_status:
            return True
        else:
            self.log.info("Tool is worn out")
            self.repair_tool(tool)

    # Judgment Durability (Pre-operation Simulation)
    def check_durability(self, tool: Tool):
        if tool.current_durability / tool.durability < (user_param.min_durability / 100):
            return False
        elif tool.current_durability < tool.durability_consumed:
            return False
        else:
            return True

    def scan_mbs(self):
        self.log.info("Check membership cards")
        mbs = self.get_mbs()
        for item in mbs:
            self.log.info(item.show(True))

        mbs = self.filter_operable(mbs)
        if not mbs:
            self.log.info("No operable membership cards found")
            return True
        self.log.info("Available membership cards:")
        for item in mbs:
            self.log.info(item.show(True))
        self.claim_mbs(mbs)
        return True

    def get_mbs(self) -> List[MBS]:
        post_data = self.table_row_template()
        post_data["table"] = "mbs"
        post_data["index_position"] = 2
        post_data["key_type"] = "i64"

        resp = self.get_table_row(post_data)
        self.log.debug("get_mbs:{0}".format(resp.text))
        resp = resp.json()
        mbs = []
        self.mbs_saved_claims = MbsSavedClaims()
        for item in resp["rows"]:
            mb = res.create_mbs(item)
            if mb:
                self.add_saved_claims(mb)
                mbs.append(mb)
            else:
                self.log.warning("Membership cards types that have not yet been supported: {0}".format(item))
        return mbs

    def add_saved_claims(self, MBS):
        if MBS.type == 'Wood':
            self.mbs_saved_claims.Wood += MBS.saved_claims
        if MBS.type == 'Food':
            self.mbs_saved_claims.Food += MBS.saved_claims
        if MBS.type == 'Gold':
            self.mbs_saved_claims.Gold += MBS.saved_claims

        self.log.debug("mbs_saved_claims: {0}".format(self.mbs_saved_claims))

    def claim_mbs(self, tools: List[MBS]):
        for item in tools:
            self.log.info("Claim membership bonus: {0}".format(item.show(True)))
            self.consume_energy(Decimal(item.energy_consumed))
            transaction = {
                "actions": [{
                    "account": "farmersworld",
                    "name": "mbsclaim",
                    "authorization": [{
                        "actor": self.wax_account,
                        "permission": "active",
                    }],
                    "data": {
                        "asset_id": item.asset_id,
                        "owner": self.wax_account,
                    },
                }],
            }
            self.wax_transact(transaction)
            self.log.info("Claim membership bonus succeed: {0}".format(item.show(more=False)))
            time.sleep(cfg.req_interval)

    def scan_withdraw(self):
        self.log.info("Check if you can withdraw")
        r = self.resoure
        # Get a cash rate
        withdraw_wood = 0
        withdraw_food = 0
        withdraw_gold = 0
        config = self.get_farming_config()
        withdraw_fee = config["fee"]
        self.log.info(f"Withdrawal fee: {withdraw_fee}% ")

        if withdraw_fee == 5:
            if r.wood > user_param.need_fww:
                withdraw_wood = r.wood - user_param.need_fww
            if r.gold > user_param.need_fwg:
                withdraw_gold = r.gold - user_param.need_fwg
            if r.food > user_param.need_fwf:
                withdraw_food = r.food - user_param.need_fwf
            if withdraw_food + withdraw_gold + withdraw_wood < user_param.withdraw_min:
                self.log.info("The withdrawal amount is too small, I will withdraw it next time")
                return True
            self.do_withdraw(withdraw_food, withdraw_gold, withdraw_wood, withdraw_fee)
            self.log.info(f"Cash: Gold[{withdraw_gold}]  Wood[{withdraw_wood}]  Food[{withdraw_food}]  Fee{withdraw_fee}】")
        else:
            self.log.info("Withdrawal fee not optimal. I will withdraw later")

        return True

    def scan_resource(self):
        r = self.get_resource()
        self.log.info(f"Gold[{r.gold}]  Wood[{r.wood}]  Food[{r.food}]  Energy[{r.energy}/{r.max_energy}]")
        self.resoure = r
        time.sleep(cfg.req_interval)
        self.token = self.get_fw_balance()
        self.log.info(f"FWG[{self.token.fwg}]  FWW[{self.token.fww}]  FWF[{self.token.fwf}]")
        if self.resoure.energy <= user_param.min_energy:
            self.log.info("The energy is less than the minimum energy configured, and the energy supplement is turned on. {0}".format(self.resoure.max_energy))
            recover = min(user_param.recover_energy, self.resoure.max_energy) - self.resoure.energy
            recover = (recover // Decimal(5)) * Decimal(5)
            self.recover_energy(recover)
            self.resoure.energy += recover

    def reset_before_scan(self):
        self.not_operational.clear()
        self.count_success_claim = 0
        self.count_error_claim = 0

    # Check crops that are cultivating, return value: Will continue running procedures
    def scan_all(self) -> int:
        status = Status.Continue
        try:
            self.reset_before_scan()
            self.log.info("Start a round of scanning")
            self.scan_resource()
            time.sleep(cfg.req_interval)

            if user_param.mbs:
                self.scan_mbs()
                time.sleep(cfg.req_interval)
            if user_param.mining:
                self.scan_mining()
                time.sleep(cfg.req_interval)
            if user_param.plant:
                self.scan_crops()
                time.sleep(cfg.req_interval)
            # Nursing cattle and chicken
            if user_param.chicken or user_param.cow:
                self.scan_animals()
                time.sleep(cfg.req_interval)
            # Breeding feeding
            if user_param.breeding:
                self.scan_breedings()
                time.sleep(cfg.req_interval)
            if user_param.withdraw:
                self.scan_withdraw()
                time.sleep(cfg.req_interval)
            if user_param.auto_deposit:
                self.scan_deposit()
                time.sleep(cfg.req_interval)
            if user_param.sell_corn or user_param.sell_barley or user_param.sell_milk or user_param.sell_egg:
                # Sell corn and barley and milk
                self.scan_nft_assets()
                time.sleep(cfg.req_interval)
            if user_param.build:
                self.scan_buildings()
                time.sleep(cfg.req_interval)
            if user_param.auto_plant:
                self.scan_plants()
                time.sleep(cfg.req_interval)
            self.log.info("Scanning finished")
            if self.not_operational:
                self.next_operate_time = min([item.next_availability for item in self.not_operational])
                self.log.info("Next operational time: {0}".format(utils.show_time(self.next_operate_time)))
                # When the operating time is up, you should delay the scan for 5 seconds to avoid problems
                self.next_operate_time += timedelta(seconds=5)
            else:
                self.next_operate_time = datetime.max
            if self.count_success_claim > 0 or self.count_error_claim > 0:
                self.log.info(f"Number of successful operations in this round: {self.count_success_claim}  Number of operation failures: {self.count_error_claim}")

            if self.count_error_claim > 0:
                self.log.info("This round has failed operations, try again later")
                self.next_scan_time = datetime.now() + cfg.min_scan_interval
            else:
                self.next_scan_time = datetime.now() + cfg.max_scan_interval

            self.next_scan_time = min(self.next_scan_time, self.next_operate_time)

            # No contract errors, clear the error counter
            self.count_error_transact = 0

        except TransactException as e:
            # self.log.exception("Intelligent contract call error")
            if not e.retry:
                return Status.Stop
            self.count_error_transact += 1
            self.log.error("Smart contract call error count [{0}]".format(self.count_error_transact))
            if self.count_error_transact >= e.max_retry_times and e.max_retry_times != -1:
                self.log.error("The contract is continuously called abnormally")
                return Status.Stop
            self.next_scan_time = datetime.now() + cfg.min_scan_interval
        except CookieExpireException as e:
            self.log.exception(str(e))
            self.log.error("Cookie failed, please restart the program manually and log in again")
            return Status.Stop
        except StopException as e:
            self.log.exception(str(e))
            self.log.error("Unrecoverable error, please handle manually, then restart the program and log in again")
            return Status.Stop
        except FarmerException as e:
            self.log.exception(str(e))
            self.log.error("General error, try again later")
            self.next_scan_time = datetime.now() + cfg.min_scan_interval
        except Exception as e:
            self.log.exception(str(e))
            self.log.error("General error, try again later")
            self.next_scan_time = datetime.now() + cfg.min_scan_interval

        self.log.info("Next scan time: {0}".format(utils.show_time(self.next_scan_time)))
        return status

    def run_forever(self):
        while True:
            if datetime.now() > self.next_scan_time:
                status = self.scan_all()
                if status == Status.Stop:
                    self.close()
                    self.log.info("The program has stopped, please restart the program manually after checking the log")
                    return 1
            time.sleep(1)


def test():
    pass


if __name__ == '__main__':
    test()
