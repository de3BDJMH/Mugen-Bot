from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any,Iterable

from src.storage.aether import AetherConfigError,load_json_object,save_json_atomic

from . import config as cfg


VERSION=1
SLOTS=("1","2","3")
DEFAULT_RULES={"1":"never","2":"never","3":"legacy"}
DEFAULT_MODES={"never","always","legacy"}
OVERRIDE_MODES=DEFAULT_MODES|{"inherit"}


class ShopRulesError(ValueError):
    pass


@dataclass(frozen=True)
class SanityRule:
    lower:int
    upper:int
    buyers:tuple[str,...]


@dataclass(frozen=True)
class ShopRules:
    default:dict[str,str]
    overrides:dict[str,dict[str,str]]
    sanity:SanityRule


@dataclass(frozen=True)
class SanityOffer:
    username:str
    item_index:int
    recovery:int
    price:int
    remaining:int


@dataclass(frozen=True)
class SanityPurchase:
    username:str
    item_index:int
    quantity:int
    recovery:int
    price:int


def shop_rules_path()->Path:
    return Path(cfg.AETHER_CONFIG_DIR)/"shop_rules.json"


def legacy_shop_rules_path()->Path:
    return Path(cfg.AETHER_DATA_DIR)/"shop_rules.json"


def default_shop_rules()->ShopRules:
    return ShopRules(
        default=dict(DEFAULT_RULES),
        overrides={},
        sanity=SanityRule(lower=0,upper=0,buyers=()),
    )


def _validate_rule_map(value:Any,*,allow_inherit:bool,require_all:bool)->dict[str,str]:
    if not isinstance(value,dict):
        raise ShopRulesError("商店槽位规则必须是 object")
    slots=set(value)
    if not all(isinstance(slot,str) for slot in slots) or not slots.issubset(SLOTS):
        raise ShopRulesError("商店槽位只能使用 1、2、3")
    if require_all and slots!=set(SLOTS):
        raise ShopRulesError("全局默认必须完整包含 1、2、3 号位")
    modes=OVERRIDE_MODES if allow_inherit else DEFAULT_MODES
    result:dict[str,str]={}
    for slot,mode in value.items():
        if not isinstance(mode,str) or mode not in modes:
            raise ShopRulesError(f"商店 {slot} 号位模式无效")
        if mode!="inherit":
            result[slot]=mode
    return result


def _validate_sanity(value:Any,owned_characters:Iterable[str]|None)->SanityRule:
    if not isinstance(value,dict) or set(value)!={"lower","upper","buyers"}:
        raise ShopRulesError("理智购买规则字段无效")
    lower=value.get("lower")
    upper=value.get("upper")
    buyers=value.get("buyers")
    if isinstance(lower,bool) or not isinstance(lower,int) or not 0<=lower<=20:
        raise ShopRulesError("理智下限必须是 0~20 的整数")
    if isinstance(upper,bool) or not isinstance(upper,int) or not lower<=upper<=20:
        raise ShopRulesError("理智上限必须是下限到 20 之间的整数")
    if not isinstance(buyers,list) or not all(isinstance(username,str) and username for username in buyers):
        raise ShopRulesError("理智购买角色必须是数组")
    if len(set(buyers))!=len(buyers):
        raise ShopRulesError("理智购买角色不能重复")
    owned=set(owned_characters) if owned_characters is not None else None
    if owned is not None:
        unknown=[username for username in buyers if username not in owned]
        if unknown:
            raise ShopRulesError(f"角色不存在或不属于当前账号：{unknown[0]}")
    return SanityRule(lower=lower,upper=upper,buyers=tuple(buyers))


def validate_shop_rules(
    default:Any,
    overrides:Any,
    sanity:Any,
    *,
    owned_characters:Iterable[str]|None=None,
)->ShopRules:
    normalized_default=_validate_rule_map(default,allow_inherit=False,require_all=True)
    if not isinstance(overrides,dict):
        raise ShopRulesError("角色覆盖规则必须是 object")
    owned=set(owned_characters) if owned_characters is not None else None
    normalized_overrides:dict[str,dict[str,str]]={}
    for username,rules in overrides.items():
        if not isinstance(username,str) or not username:
            raise ShopRulesError("角色名必须是非空字符串")
        if owned is not None and username not in owned:
            raise ShopRulesError(f"角色不存在或不属于当前账号：{username}")
        normalized=_validate_rule_map(rules,allow_inherit=True,require_all=False)
        if normalized:
            normalized_overrides[username]=normalized
    return ShopRules(
        default=normalized_default,
        overrides=normalized_overrides,
        sanity=_validate_sanity(sanity,owned_characters),
    )


def _parse_file_payload(payload:Any)->ShopRules:
    if not isinstance(payload,dict):
        raise ShopRulesError("商店购买策略文件必须是 object")
    if payload.get("version")!=VERSION:
        raise ShopRulesError("商店购买策略版本无效")
    if set(payload)!={"version","default","characters","sanity"}:
        raise ShopRulesError("商店购买策略文件字段无效")
    return validate_shop_rules(payload["default"],payload["characters"],payload["sanity"])


def load_shop_rules(path:Path|None=None)->ShopRules:
    target=path or shop_rules_path()
    if path is None and not target.exists() and legacy_shop_rules_path().exists():
        target=legacy_shop_rules_path()
    if not target.exists():
        return default_shop_rules()
    try:
        return _parse_file_payload(load_json_object(target,label="Aether 商店购买策略"))
    except (AetherConfigError,ShopRulesError) as exc:
        print(f"读取商店购买策略失败，将使用默认规则：{exc}")
        return default_shop_rules()


def save_shop_rules(
    default:Any,
    overrides:Any,
    sanity:Any,
    *,
    owned_characters:Iterable[str],
    path:Path|None=None,
)->ShopRules:
    rules=validate_shop_rules(default,overrides,sanity,owned_characters=owned_characters)
    target=path or shop_rules_path()
    payload={
        "version":VERSION,
        "default":rules.default,
        "characters":rules.overrides,
        "sanity":{
            "lower":rules.sanity.lower,
            "upper":rules.sanity.upper,
            "buyers":list(rules.sanity.buyers),
        },
    }
    save_json_atomic(target,payload)
    return rules


def effective_rule(rules:ShopRules,username:str,slot_number:int)->str:
    slot=str(slot_number)
    if slot not in SLOTS:
        raise ShopRulesError("商店槽位只能使用 1、2、3")
    return rules.overrides.get(username,{}).get(slot,rules.default[slot])


def is_sanity_item(item:Any)->bool:
    return isinstance(item,dict) and item.get("type")=="sanity"


def sanity_recovery(item:Any)->int|None:
    if not is_sanity_item(item):
        return None
    recovery=item.get("sanity_gain")
    if isinstance(recovery,bool) or not isinstance(recovery,int) or recovery<=0:
        return None
    return recovery


def select_sanity_purchases(
    current_sanity:int,
    rule:SanityRule,
    offers:Iterable[SanityOffer],
    balances:dict[str,int],
)->tuple[SanityPurchase,...]:
    if current_sanity>=rule.lower or not rule.buyers:
        return ()
    available=[offer for offer in offers if offer.username in rule.buyers and offer.recovery>0 and offer.price>=0 and offer.remaining>0]
    if not available:
        return ()
    usernames=tuple(dict.fromkeys(offer.username for offer in available))
    username_index={username:index for index,username in enumerate(usernames)}
    max_recovery=max(rule.upper-current_sanity+max(offer.recovery for offer in available),rule.lower-current_sanity)
    states={(0,(0,)*len(usernames)):(0,)*len(available)}
    for offer_index,offer in enumerate(available):
        next_states=dict(states)
        buyer_index=username_index[offer.username]
        balance=max(0,int(balances.get(offer.username,0)))
        for (recovery,spent),quantities in states.items():
            affordable=(balance-spent[buyer_index])//offer.price if offer.price else offer.remaining
            maximum=min(offer.remaining,affordable,(max_recovery-recovery)//offer.recovery)
            for quantity in range(1,maximum+1):
                updated_spent=list(spent)
                updated_spent[buyer_index]+=offer.price*quantity
                updated_quantities=list(quantities)
                updated_quantities[offer_index]=quantity
                key=(recovery+offer.recovery*quantity,tuple(updated_spent))
                next_states.setdefault(key,tuple(updated_quantities))
        states=next_states
    candidates=[]
    for (recovery,spent),quantities in states.items():
        if recovery:
            candidates.append((recovery,sum(spent),sum(quantities),quantities))
    if not candidates:
        return ()
    lower_needed=rule.lower-current_sanity
    upper_needed=rule.upper-current_sanity
    reachable=[candidate for candidate in candidates if candidate[0]>=lower_needed]
    if not reachable:
        chosen=min(candidates,key=lambda candidate:(-candidate[0],candidate[1],candidate[2]))
    else:
        within=[candidate for candidate in reachable if candidate[0]<=upper_needed]
        if within:
            chosen=min(within,key=lambda candidate:(upper_needed-candidate[0],candidate[1],candidate[2]))
        else:
            chosen=min(reachable,key=lambda candidate:(candidate[0]-upper_needed,candidate[1],candidate[2]))
    purchases=[]
    for offer,quantity in zip(available,chosen[3]):
        if quantity:
            purchases.append(SanityPurchase(
                username=offer.username,
                item_index=offer.item_index,
                quantity=quantity,
                recovery=offer.recovery*quantity,
                price=offer.price*quantity,
            ))
    return tuple(purchases)


def build_shop_rules_payload(rules:ShopRules,characters:Iterable[str])->dict[str,Any]:
    usernames=tuple(dict.fromkeys(characters))
    overrides={username:rules.overrides[username] for username in usernames if username in rules.overrides}
    buyers=[username for username in rules.sanity.buyers if username in usernames]
    return {
        "version":VERSION,
        "characters":list(usernames),
        "default":rules.default,
        "overrides":overrides,
        "effective":{
            username:{slot:effective_rule(rules,username,int(slot)) for slot in SLOTS}
            for username in usernames
        },
        "sanity":{
            "lower":rules.sanity.lower,
            "upper":rules.sanity.upper,
            "buyers":buyers,
        },
    }
