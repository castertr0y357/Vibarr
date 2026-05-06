from django.db import models
from .shows import Show

class Recommendation(models.Model):
    source_title = models.CharField(max_length=255, help_text="Title of the show that triggered this recommendation")
    suggested_show = models.ForeignKey(Show, on_delete=models.CASCADE, related_name='recommendations')
    score = models.FloatField(default=0.0, db_index=True)
    reasoning = models.TextField(null=True, blank=True, help_text="AI generated reasoning for this suggestion")
    vibe_tags = models.CharField(max_length=255, null=True, blank=True, help_text="AI generated vibe tags (comma separated)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-score']

    @property
    def vibe_tags_list(self):
        if not self.vibe_tags: return []
        return [t.strip() for t in self.vibe_tags.split(',')]
