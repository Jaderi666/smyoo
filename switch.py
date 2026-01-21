import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry # 需要这个来做类型提示
from homeassistant.core import callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """设置 Smyoo 开关平台."""
    
    entry_id = None
    
    # 优先在 config 中查找（可能由 async_load_platform 放置）
    if config and 'config_entry_id' in config:
        entry_id = config['config_entry_id']
    # 其次在 discovery_info 中查找
    elif discovery_info and 'config_entry_id' in discovery_info:
        entry_id = discovery_info['config_entry_id']
    
    if not entry_id:
        _LOGGER.error("Config entry ID not found during platform setup.")
        return

    # 使用 ID 从 Home Assistant 存储中检索 ConfigEntry 对象
    if hasattr(hass.config_entries, 'async_get_entry'):
        entry: ConfigEntry = hass.config_entries.async_get_entry(entry_id)
    else:
        _LOGGER.error("Home Assistant core API is too old: hass.config_entries.async_get_entry is missing.")
        return
        
    if not entry:
        _LOGGER.error("Config entry not found in HA core storage for ID: %s", entry_id)
        return

    # 从 hass.data 中获取协调器和 API 客户端
    if entry.entry_id not in hass.data.get(DOMAIN, {}):
        _LOGGER.error("Data for entry %s not found in hass.data. Setup failed.", entry.entry_id)
        return
        
    component_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = component_data["coordinator"]
    api_client = component_data["api"]

    # 实体列表
    entities = []
    
    # 检查协调器数据中是否有开关数据
    # 假设查询结果是 {'switches': {device_id_1: device_info_1, ...}}
    if coordinator.data and "switches" in coordinator.data:
        for device_id, device_info in coordinator.data["switches"].items():
            entities.append(
                SmyooSwitch(coordinator, api_client, device_id, device_info)
            )

    async_add_entities(entities, True)


class SmyooSwitch(CoordinatorEntity, SwitchEntity):
    """表示 Smyoo 设备中的一个开关实体."""

    def __init__(self, coordinator, api_client, device_id, device_info):
        """初始化开关."""
        super().__init__(coordinator)
        self._api_client = api_client
        self._device_id = device_id
        
        self._attr_name = device_info.get("name", f"Smyoo Switch {device_id}")
        self._attr_unique_id = f"{DOMAIN}_{device_id}"

        # 确保调用初始状态更新
        self._is_on = False # 初始为 False，等待 _update_internal_state 更新
        self._update_internal_state()

    @property
    def is_on(self):
        """返回开关是否打开."""
        return self._is_on

    @property
    def device_info(self):
        """返回设备信息."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._attr_name,
            "manufacturer": "Smyoo",
        }

    async def async_turn_on(self, **kwargs):
        """打开开关."""
        await self._api_client.async_set_device_state(self._device_id, True)
        self._is_on = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """关闭开关."""
        await self._api_client.async_set_device_state(self._device_id, False)
        self._is_on = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self):
        """当协调器更新数据时处理更新."""
        self._update_internal_state()
        self.async_write_ha_state()

    @callback
    def _update_internal_state(self):
        """从协调器数据中更新内部状态."""
        new_data = self.coordinator.data.get("switches", {}).get(self._device_id)
        if new_data:
            # 假设状态字段是 'state'，值是 'on' 或 'off'
            self._is_on = new_data.get("state") == "on"
