import re
import tempfile
import urllib.request
import zipfile
from pkgutil import get_data

from gourmand.gdebug import TimeAction
from gourmand.i18n import _

from .parser_data import ABBREVS, ABBREVS_STRT, FOOD_GROUPS, NUTRITION_FIELDS, WEIGHT_FIELDS

expander_regexp = None


def compile_expander_regexp():
    regexp = r"(?<!\w)("
    regexp += "|".join(list(ABBREVS.keys()))
    regexp += r")(?!\w)"
    return re.compile(regexp)


def expand_abbrevs(line):
    """Expand standard abbreviations."""
    global expander_regexp
    for k, v in list(ABBREVS_STRT.items()):
        line = line.replace(k, v)
    if not expander_regexp:
        expander_regexp = compile_expander_regexp()
    ematch = expander_regexp.search(line)
    while ematch:
        matchstr = ematch.groups()[0]
        replace = ABBREVS[str(matchstr)]
        line = line[0 : ematch.start()] + replace + line[ematch.end() :]
        ematch = expander_regexp.search(line)
    return line


class DatabaseGrabber:
    USDA_ZIP_URL = "http://www.nal.usda.gov/fnic/foodcomp/Data/SR17/dnload/sr17abbr.zip"
    ABBREV_FILE_NAME = "ABBREV.txt"
    DESC_FILE_NAME = "FOOD_DES.txt"
    WEIGHT_FILE_NAME = "WEIGHT.txt"

    def __init__(self, db, show_progress=None):
        self.show_progress = show_progress
        self.db = db

    def get_zip_file(self):
        if hasattr(self, "zipfile"):
            return self.zipfile
        else:
            ofi = urllib.request.urlopen(self.USDA_ZIP_URL)
            tofi = tempfile.TemporaryFile()
            tofi.write(ofi.read())
            tofi.seek(0)
            self.zipfile = zipfile.ZipFile(tofi, "r")
            return self.zipfile

    def get_file_from_url(self, filename):
        zf = self.get_zip_file()
        tofi2 = tempfile.TemporaryFile()
        tofi2.write(zf.read(filename))
        tofi2.seek(0)
        return tofi2

    def get_abbrev(self) -> None:
        abbreviations = get_data("gourmand", f"data/{self.ABBREV_FILE_NAME}")
        assert abbreviations
        self.parse_abbrevfile(abbreviations)
        del self.foodgroups_by_ndbno

    def get_groups(self) -> None:
        self.group_dict = {}
        self.foodgroups_by_ndbno = {}

        # TODO: Convert FOOD_DES.txt to UTF-8
        groups = get_data("gourmand", f"data/{self.DESC_FILE_NAME}").decode("iso-8859-1")
        assert groups
        for line in groups.splitlines():
            flds = line.split("^")
            ndbno = int(flds[0].strip("~"))
            grpno = int(flds[1].strip("~"))
            self.foodgroups_by_ndbno[ndbno] = grpno

    def get_weight(self) -> None:
        weights = get_data("gourmand", f"data/{self.WEIGHT_FILE_NAME}")
        assert weights
        self.parse_weightfile(weights)

    def grab_data(self) -> None:
        self.db.changed = True
        self.get_groups()
        self.get_abbrev()
        self.get_weight()

    def parse_line(self, line, field_defs, split_on="^"):
        """Handed a line and field definitions, return a dictionary of
        the line parsed.

        The line is a line with fields split on '^'

        field_defs is a list of entries for each field in our data.
        [(long_name,short_name,type),(long_name,short_name,type),...]

        Our dictionary will be in the form:

        {short_name : value,
         short_name : value,
         ...}
        """
        d = {}
        fields = line.split("^")
        for n, fl in enumerate(fields):
            try:
                lname, sname, typ = field_defs[n]
            except IndexError:
                print(n, fields[n], "has no definition in ", field_defs, len(field_defs))
                print("Ignoring problem and forging ahead!")
                break
            if fl and fl[0] == "~" and fl[-1] == "~":
                d[sname] = fl[1:-1]
            if typ == "float":
                try:
                    d[sname] = float(d.get(sname, fl))
                except Exception:
                    d[sname] = None
            elif typ == "int":
                try:
                    d[sname] = int(float(d.get(sname, fl)))
                except Exception:
                    if d.get(sname, fl):
                        print(d.get(sname, fl), "is not an integer")
                        raise
                    # If it's nothing, we don't bother...
                    if sname in d:
                        del d[sname]
        return d

    def parse_abbrevfile(self, abbrevfile):
        if self.show_progress:
            self.show_progress(float(0.03), _("Parsing nutritional data..."))
        self.datafile = tempfile.TemporaryFile()
        ll = abbrevfile.splitlines()
        tot = len(ll)
        n = 0
        for n, line in enumerate(ll):
            # TODO: Convert ABBREV.txt to UTF-8
            line = str(line.decode("iso-8859-1"))
            tline = TimeAction("1 line iteration", 2)
            t = TimeAction("split fields", 2)
            d = self.parse_line(line, NUTRITION_FIELDS)
            d["desc"] = expand_abbrevs(d["desc"])
            d["foodgroup"] = FOOD_GROUPS[self.foodgroups_by_ndbno[d["ndbno"]]]
            t.end()
            if self.show_progress and n % 50 == 0:
                self.show_progress(float(n) / tot, _("Reading nutritional data: imported %s of %s entries.") % (n, tot))
            t = TimeAction("append to db", 3)
            try:
                self.db.do_add_fast(self.db.nutrition_table, d)
            except Exception:
                try:
                    SQL = "UPDATE " + self.db.nutrition_table.name + " SET "
                    args = d.copy()
                    del args["ndbno"]
                    SQL += ", ".join("%s = ?" % k for k in args)
                    SQL += " WHERE ndbno = %s" % d["ndbno"]
                    # if d['ndbno']==1123:
                    #    print SQL,args.values()
                    self.db.extra_connection.execute(SQL, list(args.values()))
                except:
                    print("Error appending to nutrition_table", d)
                    print("Tried modifying table -- that failed too!")
                    raise
            t.end()
            tline.end()
        self.db.commit_fast_adds()

    def parse_weightfile(self, weightfile):
        if self.show_progress:
            self.show_progress(float(0.03), _("Parsing weight data..."))
        ll = weightfile.splitlines()
        tot = len(ll)
        n = 0
        for n, line in enumerate(ll):
            # TODO: Convert WEIGHT.txt to UTF-8
            line = str(line.decode("iso-8859-1"))
            if self.show_progress and n % 50 == 0:
                self.show_progress(float(n) / tot, _("Reading weight data for nutritional items: imported %s of %s entries") % (n, tot))
            d = self.parse_line(line, WEIGHT_FIELDS)
            if "stdev" in d:
                del d["stdev"]
            try:
                self.db.do_add_fast(self.db.usda_weights_table, d)
            except:
                print("Error appending ", d, "to usda_weights_table")
                raise
        self.db.commit_fast_adds()


if __name__ == "__main__":
    tot_prog = 0

    def show_prog(perc, msg):
        perc = perc * 100
        if perc - tot_prog:
            print("|" * int(perc - tot_prog))

    print("getting our recipe database")
    import gourmand.recipeManager

    db = gourmand.recipeManager.RecipeManager(**gourmand.recipeManager.dbargs)
    print("getting our grabber ready")
    grabber = DatabaseGrabber(db, show_prog)
    print("grabbing recipes!")
    grabber.grab_data("/home/tom/Projects/grm/data/")
    # grabber.parse_weightfile(open('/home/tom/Projects/grm/data/WEIGHT.txt','r'))
    # grabber.get_weight('/home/tom/Projects/nutritional_data/WEIGHT.txt')
