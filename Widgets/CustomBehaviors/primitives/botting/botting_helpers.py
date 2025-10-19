from collections.abc import Callable, Generator
import time
from typing import Any
from Py4GWCoreLib import Player, Item, ItemArray, Bags, Routines
from Py4GWCoreLib.AgentArray import AgentArray
from Py4GWCoreLib.GlobalCache import GLOBAL_CACHE
from Py4GWCoreLib.enums_src.GameData_enums import Range
from Py4GWCoreLib.enums_src.Multiboxing_enums import SharedCommandType
from Py4GWCoreLib.py4gwcorelib_src.FSM import FSM
from Py4GWCoreLib.py4gwcorelib_src.Lootconfig_src import LootConfig
from Py4GWCoreLib.py4gwcorelib_src.Timer import ThrottledTimer

from Widgets.CustomBehaviors.primitives.bus.event_type import EventType
from Widgets.CustomBehaviors.primitives.helpers import custom_behavior_helpers


class BottingHelpers:
    
    @staticmethod
    def wrapper(action: Generator[Any, Any, bool], on_failure: Callable[[], Generator[Any, Any, Any]]) -> Generator[Any, Any, bool]:
        result: bool = yield from action
        if result is False:
            yield from on_failure()
        return result
    
    @staticmethod
    def wait_until_on_map(target_map_id: int, timeout_ms: int) -> Generator[Any, Any, bool]:
        """Wait until we are on the target map or timeout occurs."""
        timeout = ThrottledTimer(timeout_ms)

        while not timeout.IsExpired():
            if GLOBAL_CACHE.Map.GetMapID() == target_map_id:
                return True
            yield from custom_behavior_helpers.Helpers.wait_for(100)
        return False

    @staticmethod
    def wait_until_item_looted(item_name: str, timeout_ms: int) -> Generator[Any, Any, bool]:
        """Wait until a specific item is looted into inventory or timeout occurs."""
        
        timeout = ThrottledTimer(timeout_ms)

        def search_item_id_by_name(item_name: str) -> int | None:
            item_array = GLOBAL_CACHE.AgentArray.GetItemArray()
            item_array = AgentArray.Filter.ByDistance(item_array, GLOBAL_CACHE.Player.GetXY(), Range.Spirit.value)
            for item_id in item_array:
                name = GLOBAL_CACHE.Agent.GetName(item_id)
                # print(f"item {name}")

                # Clean both strings to remove non-printable characters (like NULL bytes) and whitespace
                name_cleaned = ''.join(char for char in name if char.isprintable()).strip()
                item_name_cleaned = ''.join(char for char in item_name if char.isprintable()).strip()
                
                # Check if the cleaned strings match
                if name_cleaned == item_name_cleaned:
                    print("item found")
                    # item found
                    return item_id
            return None

        while not timeout.IsExpired():
            print(f"looking for {item_name}")
            item_id:int | None = search_item_id_by_name(item_name)

            if item_id is None:
                yield from custom_behavior_helpers.Helpers.wait_for(100)
                continue

            # LOOT
            pos = GLOBAL_CACHE.Agent.GetXY(item_id)
            follow_success = yield from Routines.Yield.Movement.FollowPath([pos], timeout=6_000)
            if not follow_success:
                print("Failed to follow path to loot item, next attempt.")
                yield from custom_behavior_helpers.Helpers.wait_for(1000)
                continue
            
            GLOBAL_CACHE.Player.Interact(item_id, call_target=False)
            yield from custom_behavior_helpers.Helpers.wait_for(100)

            # ENSURE LOOT IS LOOTED
            pickup_timer = ThrottledTimer(3_000)
            while not pickup_timer.IsExpired():
                item_id = search_item_id_by_name(item_name)
                if item_id is None: 
                    return True
                
                # Yield control to prevent freezing and allow game state updates
                yield from custom_behavior_helpers.Helpers.wait_for(50)

        print(f"Nothing to loot after ({timeout_ms}ms), exiting.")
        return False

    @staticmethod
    def wait_until_party_resign(timeout_ms: int) -> Generator[Any, Any, bool]:

        timeout = ThrottledTimer(timeout_ms)
        loop_counter = 0
        while not timeout.IsExpired():

            if GLOBAL_CACHE.Map.IsOutpost(): return True
            if GLOBAL_CACHE.Party.IsPartyDefeated(): return True

            accounts = GLOBAL_CACHE.ShMem.GetAllAccountData()
            sender_email = GLOBAL_CACHE.Player.GetAccountEmail()
            for account in accounts:
                print("Resigning account: " + account.AccountEmail)
                GLOBAL_CACHE.ShMem.SendMessage(sender_email, account.AccountEmail, SharedCommandType.Resign, (0,0,0,0))
                yield from Routines.Yield.wait(50)
            yield from Routines.Yield.wait(4_000)

            loop_counter += 1
            if loop_counter > 4:
                print(f"Resign attempts is too high ({loop_counter}), exiting.")
                return False

        yield
        print(f"Resign duration too long (>{timeout_ms}ms), exiting.")
        return False