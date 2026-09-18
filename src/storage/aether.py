from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any


_WRITE_LOCK=threading.Lock()


class AetherConfigError(ValueError):
    pass


def load_json_object(path:Path,*,label:str)->dict[str,Any]:
    try:
        with path.open("r",encoding="utf-8") as file:
            value=json.load(file)
    except FileNotFoundError as exc:
        raise AetherConfigError(f"缺少{label}：{path}") from exc
    except (OSError,UnicodeDecodeError,json.JSONDecodeError) as exc:
        raise AetherConfigError(f"读取{label}失败：{exc}") from exc
    if not isinstance(value,dict):
        raise AetherConfigError(f"{label}顶层必须是 object")
    return value


def save_json_atomic(path:Path,payload:dict[str,Any])->None:
    with _WRITE_LOCK:
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_name(path.name+".tmp")
        try:
            with temporary.open("w",encoding="utf-8") as file:
                json.dump(payload,file,ensure_ascii=False,indent=2)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary,path)
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise
