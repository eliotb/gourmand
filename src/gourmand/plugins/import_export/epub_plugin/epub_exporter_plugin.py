from gourmand.i18n import _
from gourmand.plugin import ExporterPlugin

from . import epub_exporter

EPUBFILE = _("Epub File")


class EpubExporterPlugin(ExporterPlugin):
    label = _("Exporting epub")
    sublabel = _("Exporting recipes an epub file in directory %(file)s")
    single_completed_string = _("Recipe saved as epub file %(file)s")
    filetype_desc = EPUBFILE
    saveas_filters = [EPUBFILE, ["application/epub+zip"], ["*.epub"]]
    saveas_single_filters = [EPUBFILE, ["application/epub+zip"], ["*.epub"]]
    mode = "wb"  # Epub is a zip file, so we need a binary output file

    def get_multiple_exporter(self, args):
        return epub_exporter.website_exporter(
            args["rd"],
            args["rv"],
            args["file"],
            # args['conv'],
        )

    def do_single_export(self, args):
        e = epub_exporter.website_exporter(args["rd"], [args["rec"]], args["out"], mult=args["mult"], change_units=args["change_units"], conv=args["conv"])
        e.run()

    def run_extra_prefs_dialog(self):
        pass
