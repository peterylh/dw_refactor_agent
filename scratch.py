from config import get_naming_config
import pprint
nc = get_naming_config("shop", "naming_config_enterprise.yaml")
td = nc.types.get("BIZ_PROCESS")
print(repr(td.regex), "_" in (td.regex or ""))
