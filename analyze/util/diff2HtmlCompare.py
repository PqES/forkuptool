# MIT License
#
# Copyright (c) 2016 Alex Goodman
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
# of the Software, and to permit persons to whom the Software is furnished to do
# so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import io
import os
import sys
import difflib
import argparse
import pygments
import webbrowser
from pygments.lexers import guess_lexer_for_filename
from pygments.lexer import RegexLexer
from pygments.formatters import HtmlFormatter
from pygments.token import *

# Monokai is not quite right yet
PYGMENTS_STYLES = ["vs", "xcode"] 

HTML_TEMPLATE = """
<!DOCTYPE html>
<html class="no-js">
    <head>
        <!-- 
          html_title:    browser tab title
          reset_css:     relative path to reset css file
          pygments_css:  relative path to pygments css file
          diff_css:      relative path to diff layout css file
          page_title:    title shown at the top of the page. This should be the filename of the files being diff'd
          original_code: full html contents of original file
          modified_code: full html contents of modified file
          jquery_js:     path to jquery.min.js
          diff_js:       path to diff.js
        -->
        <meta charset="utf-8">
        <title>
            %(html_title)s
        </title>
        <meta name="description" content="">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta name="mobile-web-app-capable" content="yes">
        <style>###reset_css###</style>
        <style>###diff_css###</style>
        <style>###pygments_css###</style>

    </head>
    <body>
        <div class="" id="topbar">
          <div id="filetitle"> 
            %(page_title)s
          </div>
          <div class="switches">
            <div class="switch">
              <input id="showoriginal" class="toggle toggle-yes-no menuoption" type="checkbox" checked>
              <label for="showoriginal" data-on="&#10004; Original" data-off="Original"></label>
            </div>
            <div class="switch">
              <input id="showmodified" class="toggle toggle-yes-no menuoption" type="checkbox" checked>
              <label for="showmodified" data-on="&#10004; Modified" data-off="Modified"></label>
            </div>
            <div class="switch">
              <input id="highlight" class="toggle toggle-yes-no menuoption" type="checkbox" checked>
              <label for="highlight" data-on="&#10004; Highlight" data-off="Highlight"></label>
            </div>
            <div class="switch">
              <input id="codeprintmargin" class="toggle toggle-yes-no menuoption" type="checkbox" checked>
              <label for="codeprintmargin" data-on="&#10004; Margin" data-off="Margin"></label>
            </div>
            <div class="switch">
              <input id="dosyntaxhighlight" class="toggle toggle-yes-no menuoption" type="checkbox" checked>
              <label for="dosyntaxhighlight" data-on="&#10004; Syntax" data-off="Syntax"></label>
            </div>
          </div>
        </div>
        <div id="maincontainer" class="%(page_width)s">
            <div id="leftcode" class="left-inner-shadow codebox divider-outside-bottom">
                <div class="codefiletab">
                    &#10092; Original
                </div>
                <div class="printmargin">
                    01234567890123456789012345678901234567890123456789012345678901234567890123456789
                </div>
                %(original_code)s
            </div>
            <div id="rightcode" class="left-inner-shadow codebox divider-outside-bottom">
                <div class="codefiletab">
                    &#10093; Modified
                </div>
                <div class="printmargin">
                    01234567890123456789012345678901234567890123456789012345678901234567890123456789
                </div>
                %(modified_code)s
            </div>
        </div>
<script>###jquery_js###</script>
<script>###diff_js###</script>
    </body>
</html>
"""


class DefaultLexer(RegexLexer):
    """
    Simply lex each line as a token.
    """

    name = 'Default'
    aliases = ['default']
    filenames = ['*']

    tokens = {
        'root': [
            (r'.*\n', Text),
        ]
    }


class DiffHtmlFormatter(HtmlFormatter):
    """
    Formats a single source file with pygments and adds diff highlights based on the 
    diff details given.
    """
    isLeft = False
    diffs = None

    def __init__(self, isLeft, diffs, *args, **kwargs):
        self.isLeft = isLeft
        self.diffs = diffs
        super(DiffHtmlFormatter, self).__init__(*args, **kwargs)

    def wrap(self, source, outfile):
        return self._wrap_code(source)

    def getDiffLineNos(self):
        retlinenos = []
        for idx, ((left_no, left_line), (right_no, right_line), change) in enumerate(self.diffs):
            no = None
            if self.isLeft:
                if change:
                    if isinstance(left_no, int) and isinstance(right_no, int):
                        no = '<span class="lineno_q lineno_leftchange">' + \
                            str(left_no) + "</span>"
                    elif isinstance(left_no, int) and not isinstance(right_no, int):
                        no = '<span class="lineno_q lineno_leftdel">' + \
                            str(left_no) + "</span>"
                    elif not isinstance(left_no, int) and isinstance(right_no, int):
                        no = '<span class="lineno_q lineno_leftadd">  </span>'
                else:
                    no = '<span class="lineno_q">' + str(left_no) + "</span>"
            else:
                if change:
                    if isinstance(left_no, int) and isinstance(right_no, int):
                        no = '<span class="lineno_q lineno_rightchange">' + \
                            str(right_no) + "</span>"
                    elif isinstance(left_no, int) and not isinstance(right_no, int):
                        no = '<span class="lineno_q lineno_rightdel">  </span>'
                    elif not isinstance(left_no, int) and isinstance(right_no, int):
                        no = '<span class="lineno_q lineno_rightadd">' + \
                            str(right_no) + "</span>"
                else:
                    no = '<span class="lineno_q">' + str(right_no) + "</span>"

            retlinenos.append(no)

        return retlinenos

    def _wrap_code(self, source):
        source = list(source)
        yield 0, '<pre>'

        for idx, ((left_no, left_line), (right_no, right_line), change) in enumerate(self.diffs):
            # print idx, ((left_no, left_line),(right_no, right_line),change)
            try:
                if self.isLeft:
                    if change:
                        if isinstance(left_no, int) and isinstance(right_no, int) and left_no <= len(source):
                            i, t = source[left_no - 1]
                            t = '<span class="left_diff_change">' + t + "</span>"
                        elif isinstance(left_no, int) and not isinstance(right_no, int) and left_no <= len(source):
                            i, t = source[left_no - 1]
                            t = '<span class="left_diff_del">' + t + "</span>"
                        elif not isinstance(left_no, int) and isinstance(right_no, int):
                            i, t = 1, left_line
                            t = '<span class="left_diff_add">' + t + "</span>"
                        else:
                            raise
                    else:
                        if left_no <= len(source):
                            i, t = source[left_no - 1]
                        else:
                            i = 1
                            t = left_line
                else:
                    if change:
                        if isinstance(left_no, int) and isinstance(right_no, int) and right_no <= len(source):
                            i, t = source[right_no - 1]
                            t = '<span class="right_diff_change">' + t + "</span>"
                        elif isinstance(left_no, int) and not isinstance(right_no, int):
                            i, t = 1, right_line
                            t = '<span class="right_diff_del">' + t + "</span>"
                        elif not isinstance(left_no, int) and isinstance(right_no, int) and right_no <= len(source):
                            i, t = source[right_no - 1]
                            t = '<span class="right_diff_add">' + t + "</span>"
                        else:
                            raise
                    else:
                        if right_no <= len(source):
                            i, t = source[right_no - 1]
                        else:
                            i = 1
                            t = right_line
                yield i, t
            except:
                # print "WARNING! failed to enumerate diffs fully!"
                pass  # this is expected sometimes
        yield 0, '\n</pre>'

    def _wrap_tablelinenos(self, inner):
        dummyoutfile = io.StringIO()
        lncount = 0
        for t, line in inner:
            if t:
                lncount += 1

            # compatibility Python v2/v3
            if sys.version_info > (3,0):
                dummyoutfile.write(line)
            else:
                dummyoutfile.write(unicode(line))

        fl = self.linenostart
        mw = len(str(lncount + fl - 1))
        sp = self.linenospecial
        st = self.linenostep
        la = self.lineanchors
        aln = self.anchorlinenos
        nocls = self.noclasses

        lines = []
        for i in self.getDiffLineNos():
            lines.append('%s' % (i,))

        ls = ''.join(lines)

        # in case you wonder about the seemingly redundant <div> here: since the
        # content in the other cell also is wrapped in a div, some browsers in
        # some configurations seem to mess up the formatting...
        if nocls:
            yield 0, ('<table class="%stable">' % self.cssclass +
                      '<tr><td><div class="linenodiv" '
                      'style="background-color: #f0f0f0; padding-right: 10px">'
                      '<pre style="line-height: 125%">' +
                      ls + '</pre></div></td><td class="code">')
        else:
            yield 0, ('<table class="%stable">' % self.cssclass +
                      '<tr><td class="linenos"><div class="linenodiv"><pre>' +
                      ls + '</pre></div></td><td class="code">')
        yield 0, dummyoutfile.getvalue()
        yield 0, '</td></tr></table>'


class CodeDiff(object):
    """
    Manages a pair of source files and generates a single html diff page comparing
    the contents.
    """
    pygmentsCssFile = "deps/codeformats/%s.css"
    diffCssFile = "deps/diff.css"
    diffJsFile = "deps/diff.js"
    resetCssFile = "deps/reset.css"
    jqueryJsFile = "deps/jquery.min.js"

    def __init__(self, fromfile, tofile, fromtxt=None, totxt=None, name=None):
        self.filename = name
        self.fromfile = fromfile
        if fromtxt == None:
            try:
                with io.open(fromfile) as f:
                    self.fromlines = f.readlines()
            except Exception as e:
                print("Problem reading file %s" % fromfile)
                print(e)
                sys.exit(1)
        else:
            self.fromlines = [n + "\n" for n in fromtxt.split("\n")]
        self.leftcode = "".join(self.fromlines)

        self.tofile = tofile
        if totxt == None:
            try:
                with io.open(tofile) as f:
                    self.tolines = f.readlines()
            except Exception as e:
                print("Problem reading file %s" % tofile)
                print(e)
                sys.exit(1)
        else:
            self.tolines = [n + "\n" for n in totxt.split("\n")]
        self.rightcode = "".join(self.tolines)

    def getDiffDetails(self, fromdesc='', todesc='', context=False, numlines=5, tabSize=8):
        # change tabs to spaces before it gets more difficult after we insert
        # markkup
        def expand_tabs(line):
            # hide real spaces
            line = line.replace(' ', '\0')
            # expand tabs into spaces
            line = line.expandtabs(tabSize)
            # replace spaces from expanded tabs back into tab characters
            # (we'll replace them with markup after we do differencing)
            line = line.replace(' ', '\t')
            return line.replace('\0', ' ').rstrip('\n')

        self.fromlines = [expand_tabs(line) for line in self.fromlines]
        self.tolines = [expand_tabs(line) for line in self.tolines]

        # create diffs iterator which generates side by side from/to data
        if context:
            context_lines = numlines
        else:
            context_lines = None

        diffs = difflib._mdiff(self.fromlines, self.tolines, context_lines,
                               linejunk=None, charjunk=difflib.IS_CHARACTER_JUNK)
        return list(diffs)

    def format(self, options):
        self.diffs = self.getDiffDetails(self.fromfile, self.tofile)

        if options['verbose']:
            for diff in self.diffs:
                print("%-6s %-80s %-80s" % (diff[2], diff[0], diff[1]))

        fields = ((self.leftcode, True, self.fromfile),
                  (self.rightcode, False, self.tofile))

        codeContents = []
        for (code, isLeft, filename) in fields:

            inst = DiffHtmlFormatter(isLeft,
                                     self.diffs,
                                     nobackground=False,
                                     linenos=True,
                                     style=options['syntax_css'])

            try:
                self.lexer = guess_lexer_for_filename(self.filename, code)

            except pygments.util.ClassNotFound:
                if options['verbose']:
                    print("No Lexer Found! Using default...")

                self.lexer = DefaultLexer()

            formatted = pygments.highlight(code, self.lexer, inst)

            codeContents.append(formatted)

        answers = {
            "html_title":     self.filename,
            "reset_css":      self.resetCssFile,
            "pygments_css":   self.pygmentsCssFile % options['syntax_css'],
            "diff_css":       self.diffCssFile,
            "page_title":     self.filename,
            "original_code":  codeContents[0],
            "modified_code":  codeContents[1],
            "jquery_js":      self.jqueryJsFile,
            "diff_js":        self.diffJsFile,
            "page_width":     "page-80-width" if options['print_width'] else "page-full-width"
        }

        string_reset_css = ''
        f = open(os.path.abspath('analyze/util/'+self.resetCssFile), 'r')
        string_reset_css = f.read()
        f.close

        string_pygments_css = ''
        f = open(os.path.abspath('analyze/util/'+self.pygmentsCssFile % options['syntax_css']), 'r')
        string_pygments_css = f.read()
        f.close

        string_diff_css = ''
        f = open(os.path.abspath('analyze/util/'+self.diffCssFile), 'r')
        string_diff_css = f.read()
        f.close

        string_jquery_js = ''
        f = open(os.path.abspath('analyze/util/'+self.jqueryJsFile), 'r')
        string_jquery_js = f.read()
        f.close

        string_diff_js = ''
        f = open(os.path.abspath('analyze/util/'+self.diffJsFile), 'r')
        string_diff_js = f.read()
        f.close

        self.htmlContents = HTML_TEMPLATE % answers
        self.htmlContents = self.htmlContents.replace('###reset_css###',string_reset_css)
        self.htmlContents = self.htmlContents.replace('###pygments_css###',string_pygments_css)
        self.htmlContents = self.htmlContents.replace('###diff_css###',string_diff_css)
        self.htmlContents = self.htmlContents.replace('###jquery_js###',string_jquery_js)
        self.htmlContents = self.htmlContents.replace('###diff_js###',string_diff_js)

    def write(self, path):
        fh = io.open(path, 'w')
        fh.write(self.htmlContents)
        fh.close()

    def getHtmlContents():
        return self.htmlContents


def showDiff(outputpath):
    path = os.path.abspath(outputpath)
    webbrowser.open('file://' + path)


def generateDiff2Html(file1, file2):
    options = {
        "verbose": False,
        "syntax_css": "vs",
        "print_width": None,
    }
    codeDiff = CodeDiff(file1, file2, name=file2)
    codeDiff.format(options)
    outputpath = os.path.abspath('./analyze/templates/diff.html')
    codeDiff.write(outputpath)
    return outputpath
