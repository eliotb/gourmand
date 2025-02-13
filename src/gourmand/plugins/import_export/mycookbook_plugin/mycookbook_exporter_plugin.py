from gourmand.i18n import _
from gourmand.plugin import ExporterPlugin

from . import mycookbook_exporter

MCB = _("My CookBook MCB File")


class MCBExporterPlugin(ExporterPlugin):

    label = _("MCB Export")
    sublabel = _("Exporting recipes to My CookBook MCB file %(file)s.")
    single_completed_string = (_("Recipe saved in My CookBook MCB file %(file)s."),)
    filetype_desc = MCB
    saveas_filters = [MCB, ["application/zip"], ["*.mcb", "*.MCB"]]
    saveas_single_filters = saveas_filters

    def get_multiple_exporter(self, args):

        return mycookbook_exporter.recipe_table_to_xml(
            args["rd"],
            args["rv"],
            args["file"],
        )

    def do_single_export(self, args):
        e = mycookbook_exporter.recipe_table_to_xml(args["rd"], [args["rec"]], args["out"], change_units=args["change_units"], mult=args["mult"])
        e.run()

    def run_extra_prefs_dialog(self):
        pass
