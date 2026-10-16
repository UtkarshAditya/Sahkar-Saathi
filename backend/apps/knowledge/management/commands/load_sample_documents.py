"""Load the sample library entries, but only into an empty Document table.

Unlike ``loaddata``, this never overwrites documents someone added or edited in the
admin site, so it is safe to run on every container start. Member B's ingest command
replaces these samples with the verified corpus.
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.knowledge.models import Document


class Command(BaseCommand):
    help = "Load fixtures/sample_documents.json if the Document table is empty."

    def handle(self, *args, **options):
        if Document.objects.exists():
            self.stdout.write("load_sample_documents: documents already present, skipping.")
            return
        call_command("loaddata", "sample_documents", verbosity=0)
        count = Document.objects.count()
        self.stdout.write(self.style.SUCCESS(f"load_sample_documents: loaded {count} samples."))
