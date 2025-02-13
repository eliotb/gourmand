import re

from gourmand import check_encodings
from gourmand.gdebug import debug
from gourmand.i18n import _
from gourmand.importers import importer


class TextImporter(importer.Importer):
    ATTR_DICT = {
        "Recipe By": "source",
        "Serving Size": "servings",
        "Preparation Time": "preptime",
        "Categories": "category",
    }

    end_of_paragraph_length = 60

    def __init__(self, filename, conv=None):
        self.fn = filename
        self.rec = {}
        self.ing = {}
        self.compile_regexps()
        self.lines = None
        importer.Importer.__init__(self, conv=conv)

    def pre_run(self):
        self.lines = check_encodings.get_file(self.fn)

        if self.lines is None:
            return  # The operation has been cancelled

        self.total_lines = len(self.lines)
        print("we have ", self.total_lines, "lines in file", self.fn)

    def do_run(self):
        if self.lines is None:
            return

        for n in range(self.total_lines):
            line = self.lines[n]
            if n % 15 == 0:
                prog = float(n) / float(self.total_lines)
                msg = _("Imported %s recipes.") % (len(self.added_recs))
                self.emit("progress", prog, msg)
            self.handle_line(line)
        # commit the last rec if need be
        if self.rec:
            self.commit_rec()
        importer.Importer.do_run(self)

    def handle_line(self, line):
        raise NotImplementedError

    def compile_regexps(self):
        self.blank_matcher = re.compile(r"^\s*$")
        # out unwrap regexp looks for a line with no meaningful characters, or a line that starts in
        # ALLCAPS or a line that is only space. (we use this with .split() to break text up into
        # paragraph breaks.
        self.unwrap_matcher = re.compile(r"\n\W*\n")
        self.find_header_breaks_matcher = re.compile(r"\s+(?=[A-Z][A-Z][A-Z]+:.*)")

    def unwrap_lines(self, blob):
        if blob.find("") >= 0:
            debug("Using built-in paragraph markers", 1)
            # then we have paragraph markers in the text already
            outblob = " ".join(blob.split("\n"))  # get rid of line breaks
            lines = outblob.split("")  # split text up into paragraphs
            outblob = "\n".join(lines)  # insert linebreaks where paragraphs were
            return outblob
        outblob = ""
        newline = True
        for line in blob.split("\n"):
            debug("examining %s" % line, 3)
            if re.match(r"^\W*$", line):
                # ignore repeated nonword characters (hyphens, stars, etc.)
                outblob += "\n"
                continue
            # if we have a non-word character at the start of the line,
            # we assume we need to keep the newline.
            if len(line) >= 3 and re.match(r"(\W|[0-9])", line[2]):
                debug("Match non-word character; add newline before: %s" % line, 4)
                outblob += "\n"
                outblob += line
                newline = False
                continue
            # if we are continuing an old line, we add a space
            # (because we're generally stripping all spaces when
            # we write)
            if not newline:
                outblob += " "
            hmatch = self.find_header_breaks_matcher.search(line)
            if hmatch:
                # if there's a header in the middle, we go ahead
                # and start a new line
                debug("Splitting at header in line: %s" % line, 4)
                outblob += line[: hmatch.start()]
                outblob += "\n"
                outblob += line[hmatch.start() :]
                continue
            # else...
            outblob += line.strip()
            if len(line) < self.end_of_paragraph_length:  # 60 is our hard-coded end-o-paragraph length
                debug("line < %s characters, adding newline." % self.end_of_paragraph_length, 4)
                outblob += "\n"
                newline = True
            else:
                newline = False
        return outblob


class Tester(importer.Tester):
    def __init__(self):
        from gourmand.plugins.import_export.mastercook_import_plugin.mastercook_plaintext_importer import MASTERCOOK_START_REGEXP

        importer.Tester.__init__(self, regexp=MASTERCOOK_START_REGEXP)
        self.not_me = "<[?]?(xml|mx2|RcpE|RTxt)[^>]*>"

    def test(self, filename):
        """Test file named filename.

        filename can also be a file object.
        """
        if not hasattr(self, "matcher"):
            self.matcher = re.compile(self.regexp)
            self.not_matcher = re.compile(self.not_me)
        if isinstance(self.ofi, str):
            self.ofi = open(filename, "r")
        line = self.ofi.readline()
        while line:
            if self.not_matcher.match(line):
                self.ofi.close()
                return False
            if self.matcher.match(line):
                self.ofi.close()
                return True
            line = self.ofi.readline()
        self.ofi.close()
