from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("trading", "0001_initial")]
    operations = [
        migrations.AddField(model_name="position", name="current_price", field=models.DecimalField(blank=True, decimal_places=8, max_digits=20, null=True)),
        migrations.AddField(model_name="position", name="current_profit", field=models.DecimalField(blank=True, decimal_places=4, max_digits=20, null=True)),
        migrations.AddField(model_name="position", name="last_broker_seen_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="position", name="protection_revision", field=models.PositiveIntegerField(default=1)),
    ]
