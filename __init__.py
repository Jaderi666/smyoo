import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

# 导入发现（Discovery）辅助模块，用于旧版本加载平台
from homeassistant.helpers.discovery import async_load_platform

from .const import DOMAIN, PLATFORMS
from .smyoo_api import SmyooApiClient, SmyooAuthError

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Smyoo from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    phone = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    api_client = SmyooApiClient(hass, phone, password)
    
    # 1. 登录并获取初始 Session/Token
    try:
        await api_client.async_login()
    except SmyooAuthError:
        _LOGGER.error("Failed to authenticate with Smyoo API. Please check credentials.")
        return False
    except Exception as err:
        _LOGGER.error("Error setting up Smyoo API client: %s", err)
        return False 

    # 2. 创建数据协调器
    async def async_update_data():
        """Fetch data from API."""
        try:
            # 刷新设备列表和状态
            # 注意：api_client.async_query_devices() 必须返回一个字典，
            # 格式如 {'switches': {device_id_1: device_info_1, ...}}
            return await api_client.async_query_devices()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="smyoo_coordinator",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    # 首次加载数据
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api": api_client
    }

    # 3. 加载平台 (使用 entry_id 进行兼容性加载)
    for platform in PLATFORMS:
        hass.async_create_task(
            async_load_platform(
                hass, 
                platform, 
                DOMAIN, 
                {'config_entry_id': entry.entry_id}, # 将 ID 放入 discovery_info 字典中
                entry
            )
        )

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    
    # 清理 hass.data
    if entry.entry_id in hass.data[DOMAIN]:
        # 尝试关闭 session（如果存在）
        if "api" in hass.data[DOMAIN][entry.entry_id] and \
           hasattr(hass.data[DOMAIN][entry.entry_id]["api"], "session"):
             try:
                 await hass.data[DOMAIN][entry.entry_id]["api"].session.close()
             except Exception:
                 pass # 忽略关闭错误
                 
        hass.data[DOMAIN].pop(entry.entry_id)

    # 无法保证通过 discovery 加载的平台能被 async_unload_platforms 自动卸载，
    # 但我们移除核心数据后，依赖核心的清理即可。
    return True 
