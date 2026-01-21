import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from .smyoo_api import SmyooApiClient, SmyooAuthError
from .const import DOMAIN

class SmyooConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Smyoo config flow."""
    VERSION = 1
    
    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            # Clean up phone number input for consistency
            phone = user_input[CONF_USERNAME].replace('+', '').replace('-', '').strip()
            password = user_input[CONF_PASSWORD]
            
            await self.async_set_unique_id(phone)
            self._abort_if_unique_id_configured()

            try:
                client = SmyooApiClient(self.hass, phone, password)
                await client.async_login()
                await client.session.close() # Close session after successful test login
                
                return self.async_create_entry(
                    title=f"Smyoo ({phone})",
                    data=user_input,
                )
            except SmyooAuthError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"

        data_schema = vol.Schema({
            # 要求用户输入手机号，我们会在 API 客户端中处理 +86 前缀
            vol.Required(CONF_USERNAME, description="手机号 (例如: 13071905314)"): str,
            vol.Required(CONF_PASSWORD, description="密码"): str,
        })

        return self.async_show_form(
            step_id="user", 
            data_schema=data_schema, 
            errors=errors
        )
