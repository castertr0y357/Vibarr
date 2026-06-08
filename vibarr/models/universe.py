from django.db import models

class Universe(models.Model):
    name = models.TextField(unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class UniverseMergeSuggestion(models.Model):
    source_universe = models.ForeignKey(Universe, on_delete=models.CASCADE, related_name='merge_sources')
    target_universe = models.ForeignKey(Universe, on_delete=models.CASCADE, related_name='merge_targets')
    confidence = models.IntegerField(default=5) # 1-10 scale
    reasoning = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['source_universe', 'target_universe'], name='unique_merge_suggestion')
        ]
        ordering = ['-confidence', '-created_at']
