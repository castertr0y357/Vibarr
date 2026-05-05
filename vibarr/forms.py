from django import forms
from .models import AppConfig

class AppConfigForm(forms.ModelForm):
    class Meta:
        model = AppConfig
        exclude = ['last_sync']
        widgets = {
            'plex_token': forms.PasswordInput(render_value=True),
            'jellyfin_api_key': forms.PasswordInput(render_value=True),
            'sonarr_api_key': forms.PasswordInput(render_value=True),
            'radarr_api_key': forms.PasswordInput(render_value=True),
            'tmdb_api_key': forms.PasswordInput(render_value=True),
            'telegram_bot_token': forms.PasswordInput(render_value=True),
            'ai_api_key': forms.PasswordInput(render_value=True),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to all fields
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'
