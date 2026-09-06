var e = require("node:process");

var D = require("node:readline");

var r = require("node:tty");

var t = require("node:fs/promises");

var n = require("node:path");

var i = require("node:buffer");

var a = require("node:child_process");

var s = require("fs");

var c = require("path");

var l = require("child_process");

var d = require("node:url");

var p = require("node:os");

var E = require("node:fs");

var f = require("node:timers/promises");

var h = require("stream");

var m = require("node:util");

var g = require("./index-chunk.js");

var B = require("@gql.tada/internal");

function _interopNamespaceDefault(e) {
  var D = Object.create(null);
  if (e) {
    Object.keys(e).forEach((function(r) {
      if ("default" !== r) {
        var t = Object.getOwnPropertyDescriptor(e, r);
        Object.defineProperty(D, r, t.get ? t : {
          enumerable: !0,
          get: function() {
            return e[r];
          }
        });
      }
    }));
  }
  D.default = e;
  return D;
}

var b = _interopNamespaceDefault(D);

function getDefaultExportFromCjs(e) {
  return e && e.__esModule && Object.prototype.hasOwnProperty.call(e, "default") ? e.default : e;
}

var w = "[";

var S = {
  to(e, D) {
    if (!D) {
      return `${w}${e + 1}G`;
    }
    return `${w}${D + 1};${e + 1}H`;
  },
  move(e, D) {
    var r = "";
    if (e < 0) {
      r += `${w}${-e}D`;
    } else if (e > 0) {
      r += `${w}${e}C`;
    }
    if (D < 0) {
      r += `${w}${-D}A`;
    } else if (D > 0) {
      r += `${w}${D}B`;
    }
    return r;
  },
  up: (e = 1) => `${w}${e}A`,
  down: (e = 1) => `${w}${e}B`,
  forward: (e = 1) => `${w}${e}C`,
  backward: (e = 1) => `${w}${e}D`,
  nextLine: (e = 1) => `${w}E`.repeat(e),
  prevLine: (e = 1) => `${w}F`.repeat(e),
  left: `${w}G`,
  hide: `${w}?25l`,
  show: `${w}?25h`,
  save: "7",
  restore: "8"
};

var I = {
  up: (e = 1) => `${w}S`.repeat(e),
  down: (e = 1) => `${w}T`.repeat(e)
};

var O = {
  screen: `${w}2J`,
  up: (e = 1) => `${w}1J`.repeat(e),
  down: (e = 1) => `${w}J`.repeat(e),
  line: `${w}2K`,
  lineEnd: `${w}K`,
  lineStart: `${w}1K`,
  lines(e) {
    var D = "";
    for (var r = 0; r < e; r++) {
      D += this.line + (r < e - 1 ? S.up() : "");
    }
    if (e) {
      D += S.left;
    }
    return D;
  }
};

var k = {
  cursor: S,
  scroll: I,
  erase: O,
  beep: ""
};

var G = {
  exports: {}
};

var M = String;

var create = function() {
  return {
    isColorSupported: !1,
    reset: M,
    bold: M,
    dim: M,
    italic: M,
    underline: M,
    inverse: M,
    hidden: M,
    strikethrough: M,
    black: M,
    red: M,
    green: M,
    yellow: M,
    blue: M,
    magenta: M,
    cyan: M,
    white: M,
    gray: M,
    bgBlack: M,
    bgRed: M,
    bgGreen: M,
    bgYellow: M,
    bgBlue: M,
    bgMagenta: M,
    bgCyan: M,
    bgWhite: M
  };
};

G.exports = create();

G.exports.createColors = create;

var _ = getDefaultExportFromCjs(G.exports);

function S$1(e) {
  if ("string" != typeof e) {
    throw new TypeError(`Expected a \`string\`, got \`${typeof e}\``);
  }
  return e.replace(function q$1({onlyFirst: e = !1} = {}) {
    var D = [ "[\\u001B\\u009B][[\\]()#;?]*(?:(?:(?:(?:;[-a-zA-Z\\d\\/#&.:=?%@~_]+)*|[a-zA-Z\\d]+(?:;[-a-zA-Z\\d\\/#&.:=?%@~_]*)*)?\\u0007)", "(?:(?:\\d{1,4}(?:;\\d{0,4})*)?[\\dA-PR-TZcf-ntqry=><~]))" ].join("|");
    return new RegExp(D, e ? void 0 : "g");
  }(), "");
}

function j(e) {
  return e && e.__esModule && Object.prototype.hasOwnProperty.call(e, "default") ? e.default : e;
}

var U = {
  exports: {}
};

!function() {
  var e = {};
  U.exports = e, e.eastAsianWidth = function(e) {
    var D = e.charCodeAt(0), r = 2 == e.length ? e.charCodeAt(1) : 0, t = D;
    return 55296 <= D && D <= 56319 && 56320 <= r && r <= 57343 && (t = (D &= 1023) << 10 | (r &= 1023), 
    t += 65536), 12288 == t || 65281 <= t && t <= 65376 || 65504 <= t && t <= 65510 ? "F" : 8361 == t || 65377 <= t && t <= 65470 || 65474 <= t && t <= 65479 || 65482 <= t && t <= 65487 || 65490 <= t && t <= 65495 || 65498 <= t && t <= 65500 || 65512 <= t && t <= 65518 ? "H" : 4352 <= t && t <= 4447 || 4515 <= t && t <= 4519 || 4602 <= t && t <= 4607 || 9001 <= t && t <= 9002 || 11904 <= t && t <= 11929 || 11931 <= t && t <= 12019 || 12032 <= t && t <= 12245 || 12272 <= t && t <= 12283 || 12289 <= t && t <= 12350 || 12353 <= t && t <= 12438 || 12441 <= t && t <= 12543 || 12549 <= t && t <= 12589 || 12593 <= t && t <= 12686 || 12688 <= t && t <= 12730 || 12736 <= t && t <= 12771 || 12784 <= t && t <= 12830 || 12832 <= t && t <= 12871 || 12880 <= t && t <= 13054 || 13056 <= t && t <= 19903 || 19968 <= t && t <= 42124 || 42128 <= t && t <= 42182 || 43360 <= t && t <= 43388 || 44032 <= t && t <= 55203 || 55216 <= t && t <= 55238 || 55243 <= t && t <= 55291 || 63744 <= t && t <= 64255 || 65040 <= t && t <= 65049 || 65072 <= t && t <= 65106 || 65108 <= t && t <= 65126 || 65128 <= t && t <= 65131 || 110592 <= t && t <= 110593 || 127488 <= t && t <= 127490 || 127504 <= t && t <= 127546 || 127552 <= t && t <= 127560 || 127568 <= t && t <= 127569 || 131072 <= t && t <= 194367 || 177984 <= t && t <= 196605 || 196608 <= t && t <= 262141 ? "W" : 32 <= t && t <= 126 || 162 <= t && t <= 163 || 165 <= t && t <= 166 || 172 == t || 175 == t || 10214 <= t && t <= 10221 || 10629 <= t && t <= 10630 ? "Na" : 161 == t || 164 == t || 167 <= t && t <= 168 || 170 == t || 173 <= t && t <= 174 || 176 <= t && t <= 180 || 182 <= t && t <= 186 || 188 <= t && t <= 191 || 198 == t || 208 == t || 215 <= t && t <= 216 || 222 <= t && t <= 225 || 230 == t || 232 <= t && t <= 234 || 236 <= t && t <= 237 || 240 == t || 242 <= t && t <= 243 || 247 <= t && t <= 250 || 252 == t || 254 == t || 257 == t || 273 == t || 275 == t || 283 == t || 294 <= t && t <= 295 || 299 == t || 305 <= t && t <= 307 || 312 == t || 319 <= t && t <= 322 || 324 == t || 328 <= t && t <= 331 || 333 == t || 338 <= t && t <= 339 || 358 <= t && t <= 359 || 363 == t || 462 == t || 464 == t || 466 == t || 468 == t || 470 == t || 472 == t || 474 == t || 476 == t || 593 == t || 609 == t || 708 == t || 711 == t || 713 <= t && t <= 715 || 717 == t || 720 == t || 728 <= t && t <= 731 || 733 == t || 735 == t || 768 <= t && t <= 879 || 913 <= t && t <= 929 || 931 <= t && t <= 937 || 945 <= t && t <= 961 || 963 <= t && t <= 969 || 1025 == t || 1040 <= t && t <= 1103 || 1105 == t || 8208 == t || 8211 <= t && t <= 8214 || 8216 <= t && t <= 8217 || 8220 <= t && t <= 8221 || 8224 <= t && t <= 8226 || 8228 <= t && t <= 8231 || 8240 == t || 8242 <= t && t <= 8243 || 8245 == t || 8251 == t || 8254 == t || 8308 == t || 8319 == t || 8321 <= t && t <= 8324 || 8364 == t || 8451 == t || 8453 == t || 8457 == t || 8467 == t || 8470 == t || 8481 <= t && t <= 8482 || 8486 == t || 8491 == t || 8531 <= t && t <= 8532 || 8539 <= t && t <= 8542 || 8544 <= t && t <= 8555 || 8560 <= t && t <= 8569 || 8585 == t || 8592 <= t && t <= 8601 || 8632 <= t && t <= 8633 || 8658 == t || 8660 == t || 8679 == t || 8704 == t || 8706 <= t && t <= 8707 || 8711 <= t && t <= 8712 || 8715 == t || 8719 == t || 8721 == t || 8725 == t || 8730 == t || 8733 <= t && t <= 8736 || 8739 == t || 8741 == t || 8743 <= t && t <= 8748 || 8750 == t || 8756 <= t && t <= 8759 || 8764 <= t && t <= 8765 || 8776 == t || 8780 == t || 8786 == t || 8800 <= t && t <= 8801 || 8804 <= t && t <= 8807 || 8810 <= t && t <= 8811 || 8814 <= t && t <= 8815 || 8834 <= t && t <= 8835 || 8838 <= t && t <= 8839 || 8853 == t || 8857 == t || 8869 == t || 8895 == t || 8978 == t || 9312 <= t && t <= 9449 || 9451 <= t && t <= 9547 || 9552 <= t && t <= 9587 || 9600 <= t && t <= 9615 || 9618 <= t && t <= 9621 || 9632 <= t && t <= 9633 || 9635 <= t && t <= 9641 || 9650 <= t && t <= 9651 || 9654 <= t && t <= 9655 || 9660 <= t && t <= 9661 || 9664 <= t && t <= 9665 || 9670 <= t && t <= 9672 || 9675 == t || 9678 <= t && t <= 9681 || 9698 <= t && t <= 9701 || 9711 == t || 9733 <= t && t <= 9734 || 9737 == t || 9742 <= t && t <= 9743 || 9748 <= t && t <= 9749 || 9756 == t || 9758 == t || 9792 == t || 9794 == t || 9824 <= t && t <= 9825 || 9827 <= t && t <= 9829 || 9831 <= t && t <= 9834 || 9836 <= t && t <= 9837 || 9839 == t || 9886 <= t && t <= 9887 || 9918 <= t && t <= 9919 || 9924 <= t && t <= 9933 || 9935 <= t && t <= 9953 || 9955 == t || 9960 <= t && t <= 9983 || 10045 == t || 10071 == t || 10102 <= t && t <= 10111 || 11093 <= t && t <= 11097 || 12872 <= t && t <= 12879 || 57344 <= t && t <= 63743 || 65024 <= t && t <= 65039 || 65533 == t || 127232 <= t && t <= 127242 || 127248 <= t && t <= 127277 || 127280 <= t && t <= 127337 || 127344 <= t && t <= 127386 || 917760 <= t && t <= 917999 || 983040 <= t && t <= 1048573 || 1048576 <= t && t <= 1114109 ? "A" : "N";
  }, e.characterLength = function(e) {
    var D = this.eastAsianWidth(e);
    return "F" == D || "W" == D || "A" == D ? 2 : 1;
  };
  function F(e) {
    return e.match(/[\uD800-\uDBFF][\uDC00-\uDFFF]|[^\uD800-\uDFFF]/g) || [];
  }
  e.length = function(e) {
    for (var D = F(e), r = 0, t = 0; t < D.length; t++) {
      r += this.characterLength(D[t]);
    }
    return r;
  }, e.slice = function(D, r, t) {
    textLen = e.length(D), t = t || 1, (r = r || 0) < 0 && (r = textLen + r), t < 0 && (t = textLen + t);
    for (var n = "", i = 0, a = F(D), s = 0; s < a.length; s++) {
      var c = a[s], l = e.length(c);
      if (i >= r - (2 == l ? 1 : 0)) {
        if (i + l <= t) {
          n += c;
        } else {
          break;
        }
      }
      i += l;
    }
    return n;
  };
}();

var z = j(U.exports);

var V = j((function() {
  return /\uD83C\uDFF4\uDB40\uDC67\uDB40\uDC62(?:\uDB40\uDC77\uDB40\uDC6C\uDB40\uDC73|\uDB40\uDC73\uDB40\uDC63\uDB40\uDC74|\uDB40\uDC65\uDB40\uDC6E\uDB40\uDC67)\uDB40\uDC7F|(?:\uD83E\uDDD1\uD83C\uDFFF\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFF\u200D\uD83E\uDD1D\u200D(?:\uD83D[\uDC68\uDC69]))(?:\uD83C[\uDFFB-\uDFFE])|(?:\uD83E\uDDD1\uD83C\uDFFE\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFE\u200D\uD83E\uDD1D\u200D(?:\uD83D[\uDC68\uDC69]))(?:\uD83C[\uDFFB-\uDFFD\uDFFF])|(?:\uD83E\uDDD1\uD83C\uDFFD\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFD\u200D\uD83E\uDD1D\u200D(?:\uD83D[\uDC68\uDC69]))(?:\uD83C[\uDFFB\uDFFC\uDFFE\uDFFF])|(?:\uD83E\uDDD1\uD83C\uDFFC\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFC\u200D\uD83E\uDD1D\u200D(?:\uD83D[\uDC68\uDC69]))(?:\uD83C[\uDFFB\uDFFD-\uDFFF])|(?:\uD83E\uDDD1\uD83C\uDFFB\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFB\u200D\uD83E\uDD1D\u200D(?:\uD83D[\uDC68\uDC69]))(?:\uD83C[\uDFFC-\uDFFF])|\uD83D\uDC68(?:\uD83C\uDFFB(?:\u200D(?:\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFF])|\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFF]))|\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFC-\uDFFF])|[\u2695\u2696\u2708]\uFE0F|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD]))?|(?:\uD83C[\uDFFC-\uDFFF])\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFF])|\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFF]))|\u200D(?:\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D)?\uD83D\uDC68|(?:\uD83D[\uDC68\uDC69])\u200D(?:\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67]))|\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67])|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFF\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFE])|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFE\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFD\uDFFF])|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFD\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB\uDFFC\uDFFE\uDFFF])|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFC\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB\uDFFD-\uDFFF])|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|(?:\uD83C\uDFFF\u200D[\u2695\u2696\u2708]|\uD83C\uDFFE\u200D[\u2695\u2696\u2708]|\uD83C\uDFFD\u200D[\u2695\u2696\u2708]|\uD83C\uDFFC\u200D[\u2695\u2696\u2708]|\u200D[\u2695\u2696\u2708])\uFE0F|\u200D(?:(?:\uD83D[\uDC68\uDC69])\u200D(?:\uD83D[\uDC66\uDC67])|\uD83D[\uDC66\uDC67])|\uD83C\uDFFF|\uD83C\uDFFE|\uD83C\uDFFD|\uD83C\uDFFC)?|(?:\uD83D\uDC69(?:\uD83C\uDFFB\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D(?:\uD83D[\uDC68\uDC69])|\uD83D[\uDC68\uDC69])|(?:\uD83C[\uDFFC-\uDFFF])\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D(?:\uD83D[\uDC68\uDC69])|\uD83D[\uDC68\uDC69]))|\uD83E\uDDD1(?:\uD83C[\uDFFB-\uDFFF])\u200D\uD83E\uDD1D\u200D\uD83E\uDDD1)(?:\uD83C[\uDFFB-\uDFFF])|\uD83D\uDC69\u200D\uD83D\uDC69\u200D(?:\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67]))|\uD83D\uDC69(?:\u200D(?:\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D(?:\uD83D[\uDC68\uDC69])|\uD83D[\uDC68\uDC69])|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFF\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFE\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFD\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFC\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFB\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD]))|\uD83E\uDDD1(?:\u200D(?:\uD83E\uDD1D\u200D\uD83E\uDDD1|\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFF\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFE\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFD\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFC\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFB\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD]))|\uD83D\uDC69\u200D\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC69\u200D\uD83D\uDC69\u200D(?:\uD83D[\uDC66\uDC67])|\uD83D\uDC69\u200D\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67])|(?:\uD83D\uDC41\uFE0F\u200D\uD83D\uDDE8|\uD83E\uDDD1(?:\uD83C\uDFFF\u200D[\u2695\u2696\u2708]|\uD83C\uDFFE\u200D[\u2695\u2696\u2708]|\uD83C\uDFFD\u200D[\u2695\u2696\u2708]|\uD83C\uDFFC\u200D[\u2695\u2696\u2708]|\uD83C\uDFFB\u200D[\u2695\u2696\u2708]|\u200D[\u2695\u2696\u2708])|\uD83D\uDC69(?:\uD83C\uDFFF\u200D[\u2695\u2696\u2708]|\uD83C\uDFFE\u200D[\u2695\u2696\u2708]|\uD83C\uDFFD\u200D[\u2695\u2696\u2708]|\uD83C\uDFFC\u200D[\u2695\u2696\u2708]|\uD83C\uDFFB\u200D[\u2695\u2696\u2708]|\u200D[\u2695\u2696\u2708])|\uD83D\uDE36\u200D\uD83C\uDF2B|\uD83C\uDFF3\uFE0F\u200D\u26A7|\uD83D\uDC3B\u200D\u2744|(?:(?:\uD83C[\uDFC3\uDFC4\uDFCA]|\uD83D[\uDC6E\uDC70\uDC71\uDC73\uDC77\uDC81\uDC82\uDC86\uDC87\uDE45-\uDE47\uDE4B\uDE4D\uDE4E\uDEA3\uDEB4-\uDEB6]|\uD83E[\uDD26\uDD35\uDD37-\uDD39\uDD3D\uDD3E\uDDB8\uDDB9\uDDCD-\uDDCF\uDDD4\uDDD6-\uDDDD])(?:\uD83C[\uDFFB-\uDFFF])|\uD83D\uDC6F|\uD83E[\uDD3C\uDDDE\uDDDF])\u200D[\u2640\u2642]|(?:\u26F9|\uD83C[\uDFCB\uDFCC]|\uD83D\uDD75)(?:\uFE0F|\uD83C[\uDFFB-\uDFFF])\u200D[\u2640\u2642]|\uD83C\uDFF4\u200D\u2620|(?:\uD83C[\uDFC3\uDFC4\uDFCA]|\uD83D[\uDC6E\uDC70\uDC71\uDC73\uDC77\uDC81\uDC82\uDC86\uDC87\uDE45-\uDE47\uDE4B\uDE4D\uDE4E\uDEA3\uDEB4-\uDEB6]|\uD83E[\uDD26\uDD35\uDD37-\uDD39\uDD3D\uDD3E\uDDB8\uDDB9\uDDCD-\uDDCF\uDDD4\uDDD6-\uDDDD])\u200D[\u2640\u2642]|[\xA9\xAE\u203C\u2049\u2122\u2139\u2194-\u2199\u21A9\u21AA\u2328\u23CF\u23ED-\u23EF\u23F1\u23F2\u23F8-\u23FA\u24C2\u25AA\u25AB\u25B6\u25C0\u25FB\u25FC\u2600-\u2604\u260E\u2611\u2618\u2620\u2622\u2623\u2626\u262A\u262E\u262F\u2638-\u263A\u2640\u2642\u265F\u2660\u2663\u2665\u2666\u2668\u267B\u267E\u2692\u2694-\u2697\u2699\u269B\u269C\u26A0\u26A7\u26B0\u26B1\u26C8\u26CF\u26D1\u26D3\u26E9\u26F0\u26F1\u26F4\u26F7\u26F8\u2702\u2708\u2709\u270F\u2712\u2714\u2716\u271D\u2721\u2733\u2734\u2744\u2747\u2763\u27A1\u2934\u2935\u2B05-\u2B07\u3030\u303D\u3297\u3299]|\uD83C[\uDD70\uDD71\uDD7E\uDD7F\uDE02\uDE37\uDF21\uDF24-\uDF2C\uDF36\uDF7D\uDF96\uDF97\uDF99-\uDF9B\uDF9E\uDF9F\uDFCD\uDFCE\uDFD4-\uDFDF\uDFF5\uDFF7]|\uD83D[\uDC3F\uDCFD\uDD49\uDD4A\uDD6F\uDD70\uDD73\uDD76-\uDD79\uDD87\uDD8A-\uDD8D\uDDA5\uDDA8\uDDB1\uDDB2\uDDBC\uDDC2-\uDDC4\uDDD1-\uDDD3\uDDDC-\uDDDE\uDDE1\uDDE3\uDDE8\uDDEF\uDDF3\uDDFA\uDECB\uDECD-\uDECF\uDEE0-\uDEE5\uDEE9\uDEF0\uDEF3])\uFE0F|\uD83C\uDFF3\uFE0F\u200D\uD83C\uDF08|\uD83D\uDC69\u200D\uD83D\uDC67|\uD83D\uDC69\u200D\uD83D\uDC66|\uD83D\uDE35\u200D\uD83D\uDCAB|\uD83D\uDE2E\u200D\uD83D\uDCA8|\uD83D\uDC15\u200D\uD83E\uDDBA|\uD83E\uDDD1(?:\uD83C\uDFFF|\uD83C\uDFFE|\uD83C\uDFFD|\uD83C\uDFFC|\uD83C\uDFFB)?|\uD83D\uDC69(?:\uD83C\uDFFF|\uD83C\uDFFE|\uD83C\uDFFD|\uD83C\uDFFC|\uD83C\uDFFB)?|\uD83C\uDDFD\uD83C\uDDF0|\uD83C\uDDF6\uD83C\uDDE6|\uD83C\uDDF4\uD83C\uDDF2|\uD83D\uDC08\u200D\u2B1B|\u2764\uFE0F\u200D(?:\uD83D\uDD25|\uD83E\uDE79)|\uD83D\uDC41\uFE0F|\uD83C\uDFF3\uFE0F|\uD83C\uDDFF(?:\uD83C[\uDDE6\uDDF2\uDDFC])|\uD83C\uDDFE(?:\uD83C[\uDDEA\uDDF9])|\uD83C\uDDFC(?:\uD83C[\uDDEB\uDDF8])|\uD83C\uDDFB(?:\uD83C[\uDDE6\uDDE8\uDDEA\uDDEC\uDDEE\uDDF3\uDDFA])|\uD83C\uDDFA(?:\uD83C[\uDDE6\uDDEC\uDDF2\uDDF3\uDDF8\uDDFE\uDDFF])|\uD83C\uDDF9(?:\uD83C[\uDDE6\uDDE8\uDDE9\uDDEB-\uDDED\uDDEF-\uDDF4\uDDF7\uDDF9\uDDFB\uDDFC\uDDFF])|\uD83C\uDDF8(?:\uD83C[\uDDE6-\uDDEA\uDDEC-\uDDF4\uDDF7-\uDDF9\uDDFB\uDDFD-\uDDFF])|\uD83C\uDDF7(?:\uD83C[\uDDEA\uDDF4\uDDF8\uDDFA\uDDFC])|\uD83C\uDDF5(?:\uD83C[\uDDE6\uDDEA-\uDDED\uDDF0-\uDDF3\uDDF7-\uDDF9\uDDFC\uDDFE])|\uD83C\uDDF3(?:\uD83C[\uDDE6\uDDE8\uDDEA-\uDDEC\uDDEE\uDDF1\uDDF4\uDDF5\uDDF7\uDDFA\uDDFF])|\uD83C\uDDF2(?:\uD83C[\uDDE6\uDDE8-\uDDED\uDDF0-\uDDFF])|\uD83C\uDDF1(?:\uD83C[\uDDE6-\uDDE8\uDDEE\uDDF0\uDDF7-\uDDFB\uDDFE])|\uD83C\uDDF0(?:\uD83C[\uDDEA\uDDEC-\uDDEE\uDDF2\uDDF3\uDDF5\uDDF7\uDDFC\uDDFE\uDDFF])|\uD83C\uDDEF(?:\uD83C[\uDDEA\uDDF2\uDDF4\uDDF5])|\uD83C\uDDEE(?:\uD83C[\uDDE8-\uDDEA\uDDF1-\uDDF4\uDDF6-\uDDF9])|\uD83C\uDDED(?:\uD83C[\uDDF0\uDDF2\uDDF3\uDDF7\uDDF9\uDDFA])|\uD83C\uDDEC(?:\uD83C[\uDDE6\uDDE7\uDDE9-\uDDEE\uDDF1-\uDDF3\uDDF5-\uDDFA\uDDFC\uDDFE])|\uD83C\uDDEB(?:\uD83C[\uDDEE-\uDDF0\uDDF2\uDDF4\uDDF7])|\uD83C\uDDEA(?:\uD83C[\uDDE6\uDDE8\uDDEA\uDDEC\uDDED\uDDF7-\uDDFA])|\uD83C\uDDE9(?:\uD83C[\uDDEA\uDDEC\uDDEF\uDDF0\uDDF2\uDDF4\uDDFF])|\uD83C\uDDE8(?:\uD83C[\uDDE6\uDDE8\uDDE9\uDDEB-\uDDEE\uDDF0-\uDDF5\uDDF7\uDDFA-\uDDFF])|\uD83C\uDDE7(?:\uD83C[\uDDE6\uDDE7\uDDE9-\uDDEF\uDDF1-\uDDF4\uDDF6-\uDDF9\uDDFB\uDDFC\uDDFE\uDDFF])|\uD83C\uDDE6(?:\uD83C[\uDDE8-\uDDEC\uDDEE\uDDF1\uDDF2\uDDF4\uDDF6-\uDDFA\uDDFC\uDDFD\uDDFF])|[#\*0-9]\uFE0F\u20E3|\u2764\uFE0F|(?:\uD83C[\uDFC3\uDFC4\uDFCA]|\uD83D[\uDC6E\uDC70\uDC71\uDC73\uDC77\uDC81\uDC82\uDC86\uDC87\uDE45-\uDE47\uDE4B\uDE4D\uDE4E\uDEA3\uDEB4-\uDEB6]|\uD83E[\uDD26\uDD35\uDD37-\uDD39\uDD3D\uDD3E\uDDB8\uDDB9\uDDCD-\uDDCF\uDDD4\uDDD6-\uDDDD])(?:\uD83C[\uDFFB-\uDFFF])|(?:\u26F9|\uD83C[\uDFCB\uDFCC]|\uD83D\uDD75)(?:\uFE0F|\uD83C[\uDFFB-\uDFFF])|\uD83C\uDFF4|(?:[\u270A\u270B]|\uD83C[\uDF85\uDFC2\uDFC7]|\uD83D[\uDC42\uDC43\uDC46-\uDC50\uDC66\uDC67\uDC6B-\uDC6D\uDC72\uDC74-\uDC76\uDC78\uDC7C\uDC83\uDC85\uDC8F\uDC91\uDCAA\uDD7A\uDD95\uDD96\uDE4C\uDE4F\uDEC0\uDECC]|\uD83E[\uDD0C\uDD0F\uDD18-\uDD1C\uDD1E\uDD1F\uDD30-\uDD34\uDD36\uDD77\uDDB5\uDDB6\uDDBB\uDDD2\uDDD3\uDDD5])(?:\uD83C[\uDFFB-\uDFFF])|(?:[\u261D\u270C\u270D]|\uD83D[\uDD74\uDD90])(?:\uFE0F|\uD83C[\uDFFB-\uDFFF])|[\u270A\u270B]|\uD83C[\uDF85\uDFC2\uDFC7]|\uD83D[\uDC08\uDC15\uDC3B\uDC42\uDC43\uDC46-\uDC50\uDC66\uDC67\uDC6B-\uDC6D\uDC72\uDC74-\uDC76\uDC78\uDC7C\uDC83\uDC85\uDC8F\uDC91\uDCAA\uDD7A\uDD95\uDD96\uDE2E\uDE35\uDE36\uDE4C\uDE4F\uDEC0\uDECC]|\uD83E[\uDD0C\uDD0F\uDD18-\uDD1C\uDD1E\uDD1F\uDD30-\uDD34\uDD36\uDD77\uDDB5\uDDB6\uDDBB\uDDD2\uDDD3\uDDD5]|\uD83C[\uDFC3\uDFC4\uDFCA]|\uD83D[\uDC6E\uDC70\uDC71\uDC73\uDC77\uDC81\uDC82\uDC86\uDC87\uDE45-\uDE47\uDE4B\uDE4D\uDE4E\uDEA3\uDEB4-\uDEB6]|\uD83E[\uDD26\uDD35\uDD37-\uDD39\uDD3D\uDD3E\uDDB8\uDDB9\uDDCD-\uDDCF\uDDD4\uDDD6-\uDDDD]|\uD83D\uDC6F|\uD83E[\uDD3C\uDDDE\uDDDF]|[\u231A\u231B\u23E9-\u23EC\u23F0\u23F3\u25FD\u25FE\u2614\u2615\u2648-\u2653\u267F\u2693\u26A1\u26AA\u26AB\u26BD\u26BE\u26C4\u26C5\u26CE\u26D4\u26EA\u26F2\u26F3\u26F5\u26FA\u26FD\u2705\u2728\u274C\u274E\u2753-\u2755\u2757\u2795-\u2797\u27B0\u27BF\u2B1B\u2B1C\u2B50\u2B55]|\uD83C[\uDC04\uDCCF\uDD8E\uDD91-\uDD9A\uDE01\uDE1A\uDE2F\uDE32-\uDE36\uDE38-\uDE3A\uDE50\uDE51\uDF00-\uDF20\uDF2D-\uDF35\uDF37-\uDF7C\uDF7E-\uDF84\uDF86-\uDF93\uDFA0-\uDFC1\uDFC5\uDFC6\uDFC8\uDFC9\uDFCF-\uDFD3\uDFE0-\uDFF0\uDFF8-\uDFFF]|\uD83D[\uDC00-\uDC07\uDC09-\uDC14\uDC16-\uDC3A\uDC3C-\uDC3E\uDC40\uDC44\uDC45\uDC51-\uDC65\uDC6A\uDC79-\uDC7B\uDC7D-\uDC80\uDC84\uDC88-\uDC8E\uDC90\uDC92-\uDCA9\uDCAB-\uDCFC\uDCFF-\uDD3D\uDD4B-\uDD4E\uDD50-\uDD67\uDDA4\uDDFB-\uDE2D\uDE2F-\uDE34\uDE37-\uDE44\uDE48-\uDE4A\uDE80-\uDEA2\uDEA4-\uDEB3\uDEB7-\uDEBF\uDEC1-\uDEC5\uDED0-\uDED2\uDED5-\uDED7\uDEEB\uDEEC\uDEF4-\uDEFC\uDFE0-\uDFEB]|\uD83E[\uDD0D\uDD0E\uDD10-\uDD17\uDD1D\uDD20-\uDD25\uDD27-\uDD2F\uDD3A\uDD3F-\uDD45\uDD47-\uDD76\uDD78\uDD7A-\uDDB4\uDDB7\uDDBA\uDDBC-\uDDCB\uDDD0\uDDE0-\uDDFF\uDE70-\uDE74\uDE78-\uDE7A\uDE80-\uDE86\uDE90-\uDEA8\uDEB0-\uDEB6\uDEC0-\uDEC2\uDED0-\uDED6]|(?:[\u231A\u231B\u23E9-\u23EC\u23F0\u23F3\u25FD\u25FE\u2614\u2615\u2648-\u2653\u267F\u2693\u26A1\u26AA\u26AB\u26BD\u26BE\u26C4\u26C5\u26CE\u26D4\u26EA\u26F2\u26F3\u26F5\u26FA\u26FD\u2705\u270A\u270B\u2728\u274C\u274E\u2753-\u2755\u2757\u2795-\u2797\u27B0\u27BF\u2B1B\u2B1C\u2B50\u2B55]|\uD83C[\uDC04\uDCCF\uDD8E\uDD91-\uDD9A\uDDE6-\uDDFF\uDE01\uDE1A\uDE2F\uDE32-\uDE36\uDE38-\uDE3A\uDE50\uDE51\uDF00-\uDF20\uDF2D-\uDF35\uDF37-\uDF7C\uDF7E-\uDF93\uDFA0-\uDFCA\uDFCF-\uDFD3\uDFE0-\uDFF0\uDFF4\uDFF8-\uDFFF]|\uD83D[\uDC00-\uDC3E\uDC40\uDC42-\uDCFC\uDCFF-\uDD3D\uDD4B-\uDD4E\uDD50-\uDD67\uDD7A\uDD95\uDD96\uDDA4\uDDFB-\uDE4F\uDE80-\uDEC5\uDECC\uDED0-\uDED2\uDED5-\uDED7\uDEEB\uDEEC\uDEF4-\uDEFC\uDFE0-\uDFEB]|\uD83E[\uDD0C-\uDD3A\uDD3C-\uDD45\uDD47-\uDD78\uDD7A-\uDDCB\uDDCD-\uDDFF\uDE70-\uDE74\uDE78-\uDE7A\uDE80-\uDE86\uDE90-\uDEA8\uDEB0-\uDEB6\uDEC0-\uDEC2\uDED0-\uDED6])|(?:[#\*0-9\xA9\xAE\u203C\u2049\u2122\u2139\u2194-\u2199\u21A9\u21AA\u231A\u231B\u2328\u23CF\u23E9-\u23F3\u23F8-\u23FA\u24C2\u25AA\u25AB\u25B6\u25C0\u25FB-\u25FE\u2600-\u2604\u260E\u2611\u2614\u2615\u2618\u261D\u2620\u2622\u2623\u2626\u262A\u262E\u262F\u2638-\u263A\u2640\u2642\u2648-\u2653\u265F\u2660\u2663\u2665\u2666\u2668\u267B\u267E\u267F\u2692-\u2697\u2699\u269B\u269C\u26A0\u26A1\u26A7\u26AA\u26AB\u26B0\u26B1\u26BD\u26BE\u26C4\u26C5\u26C8\u26CE\u26CF\u26D1\u26D3\u26D4\u26E9\u26EA\u26F0-\u26F5\u26F7-\u26FA\u26FD\u2702\u2705\u2708-\u270D\u270F\u2712\u2714\u2716\u271D\u2721\u2728\u2733\u2734\u2744\u2747\u274C\u274E\u2753-\u2755\u2757\u2763\u2764\u2795-\u2797\u27A1\u27B0\u27BF\u2934\u2935\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u3030\u303D\u3297\u3299]|\uD83C[\uDC04\uDCCF\uDD70\uDD71\uDD7E\uDD7F\uDD8E\uDD91-\uDD9A\uDDE6-\uDDFF\uDE01\uDE02\uDE1A\uDE2F\uDE32-\uDE3A\uDE50\uDE51\uDF00-\uDF21\uDF24-\uDF93\uDF96\uDF97\uDF99-\uDF9B\uDF9E-\uDFF0\uDFF3-\uDFF5\uDFF7-\uDFFF]|\uD83D[\uDC00-\uDCFD\uDCFF-\uDD3D\uDD49-\uDD4E\uDD50-\uDD67\uDD6F\uDD70\uDD73-\uDD7A\uDD87\uDD8A-\uDD8D\uDD90\uDD95\uDD96\uDDA4\uDDA5\uDDA8\uDDB1\uDDB2\uDDBC\uDDC2-\uDDC4\uDDD1-\uDDD3\uDDDC-\uDDDE\uDDE1\uDDE3\uDDE8\uDDEF\uDDF3\uDDFA-\uDE4F\uDE80-\uDEC5\uDECB-\uDED2\uDED5-\uDED7\uDEE0-\uDEE5\uDEE9\uDEEB\uDEEC\uDEF0\uDEF3-\uDEFC\uDFE0-\uDFEB]|\uD83E[\uDD0C-\uDD3A\uDD3C-\uDD45\uDD47-\uDD78\uDD7A-\uDDCB\uDDCD-\uDDFF\uDE70-\uDE74\uDE78-\uDE7A\uDE80-\uDE86\uDE90-\uDEA8\uDEB0-\uDEB6\uDEC0-\uDEC2\uDED0-\uDED6])\uFE0F|(?:[\u261D\u26F9\u270A-\u270D]|\uD83C[\uDF85\uDFC2-\uDFC4\uDFC7\uDFCA-\uDFCC]|\uD83D[\uDC42\uDC43\uDC46-\uDC50\uDC66-\uDC78\uDC7C\uDC81-\uDC83\uDC85-\uDC87\uDC8F\uDC91\uDCAA\uDD74\uDD75\uDD7A\uDD90\uDD95\uDD96\uDE45-\uDE47\uDE4B-\uDE4F\uDEA3\uDEB4-\uDEB6\uDEC0\uDECC]|\uD83E[\uDD0C\uDD0F\uDD18-\uDD1F\uDD26\uDD30-\uDD39\uDD3C-\uDD3E\uDD77\uDDB5\uDDB6\uDDB8\uDDB9\uDDBB\uDDCD-\uDDCF\uDDD1-\uDDDD])/g;
}));

function A(e, D = {}) {
  if ("string" != typeof e || 0 === e.length || (D = {
    ambiguousIsNarrow: !0,
    ...D
  }, 0 === (e = S$1(e)).length)) {
    return 0;
  }
  e = e.replace(V(), "  ");
  var r = D.ambiguousIsNarrow ? 1 : 2;
  var t = 0;
  for (var n of e) {
    var i = n.codePointAt(0);
    if (i <= 31 || i >= 127 && i <= 159 || i >= 768 && i <= 879) {
      continue;
    }
    switch (z.eastAsianWidth(n)) {
     case "F":
     case "W":
      t += 2;
      break;

     case "A":
      t += r;
      break;

     default:
      t += 1;
    }
  }
  return t;
}

var T = (e = 0) => D => `[${D + e}m`, P = (e = 0) => D => `[${38 + e};5;${D}m`, W = (e = 0) => (D, r, t) => `[${38 + e};2;${D};${r};${t}m`, K = {
  modifier: {
    reset: [ 0, 0 ],
    bold: [ 1, 22 ],
    dim: [ 2, 22 ],
    italic: [ 3, 23 ],
    underline: [ 4, 24 ],
    overline: [ 53, 55 ],
    inverse: [ 7, 27 ],
    hidden: [ 8, 28 ],
    strikethrough: [ 9, 29 ]
  },
  color: {
    black: [ 30, 39 ],
    red: [ 31, 39 ],
    green: [ 32, 39 ],
    yellow: [ 33, 39 ],
    blue: [ 34, 39 ],
    magenta: [ 35, 39 ],
    cyan: [ 36, 39 ],
    white: [ 37, 39 ],
    blackBright: [ 90, 39 ],
    gray: [ 90, 39 ],
    grey: [ 90, 39 ],
    redBright: [ 91, 39 ],
    greenBright: [ 92, 39 ],
    yellowBright: [ 93, 39 ],
    blueBright: [ 94, 39 ],
    magentaBright: [ 95, 39 ],
    cyanBright: [ 96, 39 ],
    whiteBright: [ 97, 39 ]
  },
  bgColor: {
    bgBlack: [ 40, 49 ],
    bgRed: [ 41, 49 ],
    bgGreen: [ 42, 49 ],
    bgYellow: [ 43, 49 ],
    bgBlue: [ 44, 49 ],
    bgMagenta: [ 45, 49 ],
    bgCyan: [ 46, 49 ],
    bgWhite: [ 47, 49 ],
    bgBlackBright: [ 100, 49 ],
    bgGray: [ 100, 49 ],
    bgGrey: [ 100, 49 ],
    bgRedBright: [ 101, 49 ],
    bgGreenBright: [ 102, 49 ],
    bgYellowBright: [ 103, 49 ],
    bgBlueBright: [ 104, 49 ],
    bgMagentaBright: [ 105, 49 ],
    bgCyanBright: [ 106, 49 ],
    bgWhiteBright: [ 107, 49 ]
  }
};

Object.keys(K.modifier);

Object.keys(K.color), Object.keys(K.bgColor);

var H = function tD() {
  var e = new Map;
  for (var [D, r] of Object.entries(K)) {
    for (var [t, n] of Object.entries(r)) {
      K[t] = {
        open: `[${n[0]}m`,
        close: `[${n[1]}m`
      }, r[t] = K[t], e.set(n[0], n[1]);
    }
    Object.defineProperty(K, D, {
      value: r,
      enumerable: !1
    });
  }
  return Object.defineProperty(K, "codes", {
    value: e,
    enumerable: !1
  }), K.color.close = "[39m", K.bgColor.close = "[49m", K.color.ansi = T(), K.color.ansi256 = P(), 
  K.color.ansi16m = W(), K.bgColor.ansi = T(10), K.bgColor.ansi256 = P(10), K.bgColor.ansi16m = W(10), 
  Object.defineProperties(K, {
    rgbToAnsi256: {
      value: (e, D, r) => e === D && D === r ? e < 8 ? 16 : e > 248 ? 231 : Math.round((e - 8) / 247 * 24) + 232 : 16 + 36 * Math.round(e / 255 * 5) + 6 * Math.round(D / 255 * 5) + Math.round(r / 255 * 5),
      enumerable: !1
    },
    hexToRgb: {
      value: e => {
        var D = /[a-f\d]{6}|[a-f\d]{3}/i.exec(e.toString(16));
        if (!D) {
          return [ 0, 0, 0 ];
        }
        var [r] = D;
        3 === r.length && (r = [ ...r ].map((e => e + e)).join(""));
        var t = Number.parseInt(r, 16);
        return [ t >> 16 & 255, t >> 8 & 255, 255 & t ];
      },
      enumerable: !1
    },
    hexToAnsi256: {
      value: e => K.rgbToAnsi256(...K.hexToRgb(e)),
      enumerable: !1
    },
    ansi256ToAnsi: {
      value: e => {
        if (e < 8) {
          return 30 + e;
        }
        if (e < 16) {
          return e - 8 + 90;
        }
        var D, r, t;
        if (e >= 232) {
          r = D = (10 * (e - 232) + 8) / 255, t = D;
        } else {
          var n = (e -= 16) % 36;
          D = Math.floor(e / 36) / 5, r = Math.floor(n / 6) / 5, t = n % 6 / 5;
        }
        var i = 2 * Math.max(D, r, t);
        if (0 === i) {
          return 30;
        }
        var a = 30 + (Math.round(t) << 2 | Math.round(r) << 1 | Math.round(D));
        return 2 === i && (a += 60), a;
      },
      enumerable: !1
    },
    rgbToAnsi: {
      value: (e, D, r) => K.ansi256ToAnsi(K.rgbToAnsi256(e, D, r)),
      enumerable: !1
    },
    hexToAnsi: {
      value: e => K.ansi256ToAnsi(K.hexToAnsi256(e)),
      enumerable: !1
    }
  }), K;
}(), Y = new Set([ "", "" ]), J = "]8;;", N = e => `${Y.values().next().value}[${e}m`, L = e => `${Y.values().next().value}${J}${e}`, y$1 = (e, D, r) => {
  var t = [ ...D ];
  var n = !1, i = !1, a = A(S$1(e[e.length - 1]));
  for (var [s, c] of t.entries()) {
    var l = A(c);
    if (a + l <= r ? e[e.length - 1] += c : (e.push(c), a = 0), Y.has(c) && (n = !0, 
    i = t.slice(s + 1).join("").startsWith(J)), n) {
      i ? "" === c && (n = !1, i = !1) : "m" === c && (n = !1);
      continue;
    }
    (a += l) === r && s < t.length - 1 && (e.push(""), a = 0);
  }
  !a && e[e.length - 1].length > 0 && e.length > 1 && (e[e.length - 2] += e.pop());
}, ED = (e, D, r = {}) => {
  if (!1 !== r.trim && "" === e.trim()) {
    return "";
  }
  var t, n, i = "";
  var a = (e => e.split(" ").map((e => A(e))))(e);
  var s = [ "" ];
  for (var [c, l] of e.split(" ").entries()) {
    !1 !== r.trim && (s[s.length - 1] = s[s.length - 1].trimStart());
    var d = A(s[s.length - 1]);
    if (0 !== c && (d >= D && (!1 === r.wordWrap || !1 === r.trim) && (s.push(""), d = 0), 
    (d > 0 || !1 === r.trim) && (s[s.length - 1] += " ", d++)), r.hard && a[c] > D) {
      var p = 1 + Math.floor((a[c] - (D - d) - 1) / D);
      Math.floor((a[c] - 1) / D) < p && s.push(""), y$1(s, l, D);
      continue;
    }
    if (d + a[c] > D && d > 0 && a[c] > 0) {
      if (!1 === r.wordWrap && d < D) {
        y$1(s, l, D);
        continue;
      }
      s.push("");
    }
    if (d + a[c] > D && !1 === r.wordWrap) {
      y$1(s, l, D);
      continue;
    }
    s[s.length - 1] += l;
  }
  !1 !== r.trim && (s = s.map((e => (e => {
    var D = e.split(" ");
    var r = D.length;
    for (;r > 0 && !(A(D[r - 1]) > 0); ) {
      r--;
    }
    return r === D.length ? e : D.slice(0, r).join(" ") + D.slice(r).join("");
  })(e))));
  var E = [ ...s.join("\n") ];
  for (var [f, h] of E.entries()) {
    if (i += h, Y.has(h)) {
      var {groups: m} = new RegExp(`(?:\\[(?<code>\\d+)m|\\${J}(?<uri>.*))`).exec(E.slice(f).join("")) || {
        groups: {}
      };
      if (void 0 !== m.code) {
        var g = Number.parseFloat(m.code);
        t = 39 === g ? void 0 : g;
      } else {
        void 0 !== m.uri && (n = 0 === m.uri.length ? void 0 : m.uri);
      }
    }
    var B = H.codes.get(Number(t));
    "\n" === E[f + 1] ? (n && (i += L("")), t && B && (i += N(B))) : "\n" === h && (t && B && (i += N(t)), 
    n && (i += L(n)));
  }
  return i;
};

function R(e, D, r) {
  return String(e).normalize().replace(/\r\n/g, "\n").split("\n").map((e => ED(e, D, r))).join("\n");
}

var X = Object.defineProperty, a$1 = (e, D, r) => (((e, D, r) => {
  D in e ? X(e, D, {
    enumerable: !0,
    configurable: !0,
    writable: !0,
    value: r
  }) : e[D] = r;
})(e, "symbol" != typeof D ? D + "" : D, r), r);

var Z = Symbol("clack:cancel");

function hD(e) {
  return e === Z;
}

function v(e, D) {
  e.isTTY && e.setRawMode(D);
}

var Q = new Map([ [ "k", "up" ], [ "j", "down" ], [ "h", "left" ], [ "l", "right" ] ]), uu = new Set([ "up", "down", "left", "right", "space", "enter" ]);

let eu = class x {
  constructor({render: D, input: r = e.stdin, output: t = e.stdout, ...n}, i = !0) {
    a$1(this, "input"), a$1(this, "output"), a$1(this, "rl"), a$1(this, "opts"), a$1(this, "_track", !1), 
    a$1(this, "_render"), a$1(this, "_cursor", 0), a$1(this, "state", "initial"), a$1(this, "value"), 
    a$1(this, "error", ""), a$1(this, "subscribers", new Map), a$1(this, "_prevFrame", ""), 
    this.opts = n, this.onKeypress = this.onKeypress.bind(this), this.close = this.close.bind(this), 
    this.render = this.render.bind(this), this._render = D.bind(this), this._track = i, 
    this.input = r, this.output = t;
  }
  prompt() {
    var e = new r.WriteStream(0);
    return e._write = (e, D, r) => {
      this._track && (this.value = this.rl.line.replace(/\t/g, ""), this._cursor = this.rl.cursor, 
      this.emit("value", this.value)), r();
    }, this.input.pipe(e), this.rl = D.createInterface({
      input: this.input,
      output: e,
      tabSize: 2,
      prompt: "",
      escapeCodeTimeout: 50
    }), D.emitKeypressEvents(this.input, this.rl), this.rl.prompt(), void 0 !== this.opts.initialValue && this._track && this.rl.write(this.opts.initialValue), 
    this.input.on("keypress", this.onKeypress), v(this.input, !0), this.output.on("resize", this.render), 
    this.render(), new Promise(((e, D) => {
      this.once("submit", (() => {
        this.output.write(k.cursor.show), this.output.off("resize", this.render), v(this.input, !1), 
        e(this.value);
      })), this.once("cancel", (() => {
        this.output.write(k.cursor.show), this.output.off("resize", this.render), v(this.input, !1), 
        e(Z);
      }));
    }));
  }
  on(e, D) {
    var r = this.subscribers.get(e) ?? [];
    r.push({
      cb: D
    }), this.subscribers.set(e, r);
  }
  once(e, D) {
    var r = this.subscribers.get(e) ?? [];
    r.push({
      cb: D,
      once: !0
    }), this.subscribers.set(e, r);
  }
  emit(e, ...D) {
    var r = this.subscribers.get(e) ?? [], t = [];
    var _loop = function(e) {
      e.cb(...D), e.once && t.push((() => r.splice(r.indexOf(e), 1)));
    };
    for (var n of r) {
      _loop(n);
    }
    for (var i of t) {
      i();
    }
  }
  unsubscribe() {
    this.subscribers.clear();
  }
  onKeypress(e, D) {
    if ("error" === this.state && (this.state = "active"), D?.name && !this._track && Q.has(D.name) && this.emit("cursor", Q.get(D.name)), 
    D?.name && uu.has(D.name) && this.emit("cursor", D.name), e && ("y" === e.toLowerCase() || "n" === e.toLowerCase()) && this.emit("confirm", "y" === e.toLowerCase()), 
    "\t" === e && this.opts.placeholder && (this.value || (this.rl.write(this.opts.placeholder), 
    this.emit("value", this.opts.placeholder))), e && this.emit("key", e.toLowerCase()), 
    "return" === D?.name) {
      if (this.opts.validate) {
        var r = this.opts.validate(this.value);
        r && (this.error = r, this.state = "error", this.rl.write(this.value));
      }
      "error" !== this.state && (this.state = "submit");
    }
    "" === e && (this.state = "cancel"), ("submit" === this.state || "cancel" === this.state) && this.emit("finalize"), 
    this.render(), ("submit" === this.state || "cancel" === this.state) && this.close();
  }
  close() {
    this.input.unpipe(), this.input.removeListener("keypress", this.onKeypress), this.output.write("\n"), 
    v(this.input, !1), this.rl.close(), this.emit(`${this.state}`, this.value), this.unsubscribe();
  }
  restoreCursor() {
    var e = R(this._prevFrame, process.stdout.columns, {
      hard: !0
    }).split("\n").length - 1;
    this.output.write(k.cursor.move(-999, -1 * e));
  }
  render() {
    var e = R(this._render(this) ?? "", process.stdout.columns, {
      hard: !0
    });
    if (e !== this._prevFrame) {
      if ("initial" === this.state) {
        this.output.write(k.cursor.hide);
      } else {
        var D = function aD(e, D) {
          if (e === D) {
            return;
          }
          var r = e.split("\n"), t = D.split("\n"), n = [];
          for (var i = 0; i < Math.max(r.length, t.length); i++) {
            r[i] !== t[i] && n.push(i);
          }
          return n;
        }(this._prevFrame, e);
        if (this.restoreCursor(), D && 1 === D?.length) {
          var r = D[0];
          this.output.write(k.cursor.move(0, r)), this.output.write(k.erase.lines(1));
          var t = e.split("\n");
          this.output.write(t[r]), this._prevFrame = e, this.output.write(k.cursor.move(0, t.length - r - 1));
          return;
        } else if (D && D?.length > 1) {
          var n = D[0];
          this.output.write(k.cursor.move(0, n)), this.output.write(k.erase.down());
          var i = e.split("\n").slice(n);
          this.output.write(i.join("\n")), this._prevFrame = e;
          return;
        }
        this.output.write(k.erase.down());
      }
      this.output.write(e), "initial" === this.state && (this.state = "active"), this._prevFrame = e;
    }
  }
};

class xD extends eu {
  get cursor() {
    return this.value ? 0 : 1;
  }
  get _value() {
    return 0 === this.cursor;
  }
  constructor(e) {
    super(e, !1), this.value = !!e.initialValue, this.on("value", (() => {
      this.value = this._value;
    })), this.on("confirm", (e => {
      this.output.write(k.cursor.move(0, -1)), this.value = e, this.state = "submit", 
      this.close();
    })), this.on("cursor", (() => {
      this.value = !this.value;
    }));
  }
}

var Du = Object.defineProperty, MD = (e, D, r) => (((e, D, r) => {
  D in e ? Du(e, D, {
    enumerable: !0,
    configurable: !0,
    writable: !0,
    value: r
  }) : e[D] = r;
})(e, D + "", r), r);

class TD extends eu {
  constructor(e) {
    super(e), MD(this, "valueWithCursor", ""), this.on("finalize", (() => {
      this.value || (this.value = e.defaultValue), this.valueWithCursor = this.value;
    })), this.on("value", (() => {
      if (this.cursor >= this.value.length) {
        this.valueWithCursor = `${this.value}${_.inverse(_.hidden("_"))}`;
      } else {
        var e = this.value.slice(0, this.cursor), D = this.value.slice(this.cursor);
        this.valueWithCursor = `${e}${_.inverse(D[0])}${D.slice(1)}`;
      }
    }));
  }
  get cursor() {
    return this._cursor;
  }
}

var ru = globalThis.process.platform.startsWith("win");

var tu = function q() {
  return "win32" !== e.platform ? "linux" !== e.env.TERM : Boolean(e.env.CI) || Boolean(e.env.WT_SESSION) || Boolean(e.env.TERMINUS_SUBLIME) || "{cmd::Cmder}" === e.env.ConEmuTask || "Terminus-Sublime" === e.env.TERM_PROGRAM || "vscode" === e.env.TERM_PROGRAM || "xterm-256color" === e.env.TERM || "alacritty" === e.env.TERM || "JetBrains-JediTerm" === e.env.TERMINAL_EMULATOR;
}(), o = (e, D) => tu ? e : D, nu = o("◆", "*"), iu = o("■", "x"), au = o("▲", "x"), su = o("◇", "o"), ou = o("┌", "T"), cu = o("│", "|"), Fu = o("└", "—"), lu = o("●", ">"), du = o("○", " "), y = e => {
  switch (e) {
   case "initial":
   case "active":
    return _.cyan(nu);

   case "cancel":
    return _.red(iu);

   case "error":
    return _.yellow(au);

   case "submit":
    return _.green(su);
  }
}, te = e => new TD({
  validate: e.validate,
  placeholder: e.placeholder,
  defaultValue: e.defaultValue,
  initialValue: e.initialValue,
  render() {
    var D = `${_.gray(cu)}\n${y(this.state)}  ${e.message}\n`, r = e.placeholder ? _.inverse(e.placeholder[0]) + _.dim(e.placeholder.slice(1)) : _.inverse(_.hidden("_")), t = this.value ? this.valueWithCursor : r;
    switch (this.state) {
     case "error":
      return `${D.trim()}\n${_.yellow(cu)}  ${t}\n${_.yellow(Fu)}  ${_.yellow(this.error)}\n`;

     case "submit":
      return `${D}${_.gray(cu)}  ${_.dim(this.value || e.placeholder)}`;

     case "cancel":
      return `${D}${_.gray(cu)}  ${_.strikethrough(_.dim(this.value ?? ""))}${this.value?.trim() ? "\n" + _.gray(cu) : ""}`;

     default:
      return `${D}${_.cyan(cu)}  ${t}\n${_.cyan(Fu)}\n`;
    }
  }
}).prompt(), se = e => {
  var D = e.active ?? "Yes", r = e.inactive ?? "No";
  return new xD({
    active: D,
    inactive: r,
    initialValue: e.initialValue ?? !0,
    render() {
      var t = `${_.gray(cu)}\n${y(this.state)}  ${e.message}\n`, n = this.value ? D : r;
      switch (this.state) {
       case "submit":
        return `${t}${_.gray(cu)}  ${_.dim(n)}`;

       case "cancel":
        return `${t}${_.gray(cu)}  ${_.strikethrough(_.dim(n))}\n${_.gray(cu)}`;

       default:
        return `${t}${_.cyan(cu)}  ${this.value ? `${_.green(lu)} ${D}` : `${_.dim(du)} ${_.dim(D)}`} ${_.dim("/")} ${this.value ? `${_.dim(du)} ${_.dim(r)}` : `${_.green(lu)} ${r}`}\n${_.cyan(Fu)}\n`;
      }
    }
  }).prompt();
}, ue = (e = "") => {
  process.stdout.write(`${_.gray(Fu)}  ${_.red(e)}\n\n`);
}, de = () => {
  var D = tu ? [ "◒", "◐", "◓", "◑" ] : [ "•", "o", "O", "0" ], r = tu ? 80 : 120;
  var t, n, i = !1, a = "";
  var u = (e = "", D = 0) => {
    a = e ?? a, i = !1, clearInterval(n);
    var r = 0 === D ? _.green(su) : 1 === D ? _.red(iu) : _.red(au);
    process.stdout.write(k.cursor.move(-999, 0)), process.stdout.write(k.erase.down(1)), 
    process.stdout.write(`${r}  ${a}\n`), t();
  }, $ = e => {
    i && u(e > 1 ? "Something went wrong" : "Canceled", e);
  };
  return process.on("uncaughtExceptionMonitor", (() => $(2))), process.on("unhandledRejection", (() => $(2))), 
  process.on("SIGINT", (() => $(1))), process.on("SIGTERM", (() => $(1))), process.on("exit", $), 
  {
    start: (s = "") => {
      i = !0, t = function WD({input: D = e.stdin, output: r = e.stdout, overwrite: t = !0, hideCursor: n = !0} = {}) {
        var i = b.createInterface({
          input: D,
          output: r,
          prompt: "",
          tabSize: 1
        });
        b.emitKeypressEvents(D, i), D.isTTY && D.setRawMode(!0);
        var C = (e, {name: n}) => {
          if ("" === String(e) && process.exit(0), !t) {
            return;
          }
          b.moveCursor(r, "return" === n ? 0 : -1, "return" === n ? -1 : 0, (() => {
            b.clearLine(r, 1, (() => {
              D.once("keypress", C);
            }));
          }));
        };
        return n && process.stdout.write(k.cursor.hide), D.once("keypress", C), () => {
          D.off("keypress", C), n && process.stdout.write(k.cursor.show), D.isTTY && !ru && D.setRawMode(!1), 
          i.terminal = !1, i.close();
        };
      }(), a = s.replace(/\.+$/, ""), process.stdout.write(`${_.gray(cu)}\n`);
      var c = 0, l = 0;
      n = setInterval((() => {
        var e = _.magenta(D[c]), r = ".".repeat(Math.floor(l)).slice(0, 3);
        process.stdout.write(k.cursor.move(-999, 0)), process.stdout.write(k.erase.down(1)), 
        process.stdout.write(`${e}  ${a}${r}`), c = c + 1 < D.length ? c + 1 : 0, l = l < D.length ? l + .125 : 0;
      }), r);
    },
    stop: u,
    message: (e = "") => {
      a = e ?? a;
    }
  };
};

var Cu = {
  exports: {}
};

var pu;

var Eu;

var fu;

var vu;

var hu;

if ("win32" === process.platform || global.TESTING_WINDOWS) {
  hu = function requireWindows() {
    if (Eu) {
      return pu;
    }
    Eu = 1;
    pu = isexe;
    isexe.sync = function sync(D, r) {
      return checkStat(e.statSync(D), D, r);
    };
    var e = s;
    function checkStat(e, D, r) {
      if (!e.isSymbolicLink() && !e.isFile()) {
        return !1;
      }
      return function checkPathExt(e, D) {
        var r = void 0 !== D.pathExt ? D.pathExt : process.env.PATHEXT;
        if (!r) {
          return !0;
        }
        if (-1 !== (r = r.split(";")).indexOf("")) {
          return !0;
        }
        for (var t = 0; t < r.length; t++) {
          var n = r[t].toLowerCase();
          if (n && e.substr(-n.length).toLowerCase() === n) {
            return !0;
          }
        }
        return !1;
      }(D, r);
    }
    function isexe(D, r, t) {
      e.stat(D, (function(e, n) {
        t(e, e ? !1 : checkStat(n, D, r));
      }));
    }
    return pu;
  }();
} else {
  hu = function requireMode() {
    if (vu) {
      return fu;
    }
    vu = 1;
    fu = isexe;
    isexe.sync = function sync(D, r) {
      return checkStat(e.statSync(D), r);
    };
    var e = s;
    function isexe(D, r, t) {
      e.stat(D, (function(e, D) {
        t(e, e ? !1 : checkStat(D, r));
      }));
    }
    function checkStat(e, D) {
      return e.isFile() && function checkMode(e, D) {
        var r = e.mode;
        var t = e.uid;
        var n = e.gid;
        var i = void 0 !== D.uid ? D.uid : process.getuid && process.getuid();
        var a = void 0 !== D.gid ? D.gid : process.getgid && process.getgid();
        var s = parseInt("100", 8);
        var c = parseInt("010", 8);
        return r & parseInt("001", 8) || r & c && n === a || r & s && t === i || r & (s | c) && 0 === i;
      }(e, D);
    }
    return fu;
  }();
}

var mu = isexe$1;

isexe$1.sync = function sync(e, D) {
  try {
    return hu.sync(e, D || {});
  } catch (e) {
    if (D && D.ignoreErrors || "EACCES" === e.code) {
      return !1;
    } else {
      throw e;
    }
  }
};

function isexe$1(e, D, r) {
  if ("function" == typeof D) {
    r = D;
    D = {};
  }
  if (!r) {
    if ("function" != typeof Promise) {
      throw new TypeError("callback not provided");
    }
    return new Promise((function(r, t) {
      isexe$1(e, D || {}, (function(e, D) {
        if (e) {
          t(e);
        } else {
          r(D);
        }
      }));
    }));
  }
  hu(e, D || {}, (function(e, t) {
    if (e) {
      if ("EACCES" === e.code || D && D.ignoreErrors) {
        e = null;
        t = !1;
      }
    }
    r(e, t);
  }));
}

var gu = "win32" === process.platform || "cygwin" === process.env.OSTYPE || "msys" === process.env.OSTYPE;

var Bu = c;

var bu = gu ? ";" : ":";

var yu = mu;

var getNotFoundError = e => Object.assign(new Error(`not found: ${e}`), {
  code: "ENOENT"
});

var getPathInfo = (e, D) => {
  var r = D.colon || bu;
  var t = e.match(/\//) || gu && e.match(/\\/) ? [ "" ] : [ ...gu ? [ process.cwd() ] : [], ...(D.path || process.env.PATH || "").split(r) ];
  var n = gu ? D.pathExt || process.env.PATHEXT || ".EXE;.CMD;.BAT;.COM" : "";
  var i = gu ? n.split(r) : [ "" ];
  if (gu) {
    if (-1 !== e.indexOf(".") && "" !== i[0]) {
      i.unshift("");
    }
  }
  return {
    pathEnv: t,
    pathExt: i,
    pathExtExe: n
  };
};

var which$1 = (e, D, r) => {
  if ("function" == typeof D) {
    r = D;
    D = {};
  }
  if (!D) {
    D = {};
  }
  var {pathEnv: t, pathExt: n, pathExtExe: i} = getPathInfo(e, D);
  var a = [];
  var step = r => new Promise(((n, i) => {
    if (r === t.length) {
      return D.all && a.length ? n(a) : i(getNotFoundError(e));
    }
    var s = t[r];
    var c = /^".*"$/.test(s) ? s.slice(1, -1) : s;
    var l = Bu.join(c, e);
    var d = !c && /^\.[\\\/]/.test(e) ? e.slice(0, 2) + l : l;
    n(subStep(d, r, 0));
  }));
  var subStep = (e, r, t) => new Promise(((s, c) => {
    if (t === n.length) {
      return s(step(r + 1));
    }
    var l = n[t];
    yu(e + l, {
      pathExt: i
    }, ((n, i) => {
      if (!n && i) {
        if (D.all) {
          a.push(e + l);
        } else {
          return s(e + l);
        }
      }
      return s(subStep(e, r, t + 1));
    }));
  }));
  return r ? step(0).then((e => r(null, e)), r) : step(0);
};

var Au = which$1;

which$1.sync = (e, D) => {
  D = D || {};
  var {pathEnv: r, pathExt: t, pathExtExe: n} = getPathInfo(e, D);
  var i = [];
  for (var a = 0; a < r.length; a++) {
    var s = r[a];
    var c = /^".*"$/.test(s) ? s.slice(1, -1) : s;
    var l = Bu.join(c, e);
    var d = !c && /^\.[\\\/]/.test(e) ? e.slice(0, 2) + l : l;
    for (var p = 0; p < t.length; p++) {
      var E = d + t[p];
      try {
        if (yu.sync(E, {
          pathExt: n
        })) {
          if (D.all) {
            i.push(E);
          } else {
            return E;
          }
        }
      } catch (e) {}
    }
  }
  if (D.all && i.length) {
    return i;
  }
  if (D.nothrow) {
    return null;
  }
  throw getNotFoundError(e);
};

var wu = {
  exports: {}
};

var pathKey$1 = (e = {}) => {
  var D = e.env || process.env;
  if ("win32" !== (e.platform || process.platform)) {
    return "PATH";
  }
  return Object.keys(D).reverse().find((e => "PATH" === e.toUpperCase())) || "Path";
};

wu.exports = pathKey$1;

wu.exports.default = pathKey$1;

var xu = c;

var Su = Au;

var $u = wu.exports;

function resolveCommandAttempt(e, D) {
  var r = e.options.env || process.env;
  var t = process.cwd();
  var n = null != e.options.cwd;
  var i = n && void 0 !== process.chdir && !process.chdir.disabled;
  if (i) {
    try {
      process.chdir(e.options.cwd);
    } catch (e) {}
  }
  var a;
  try {
    a = Su.sync(e.command, {
      path: r[$u({
        env: r
      })],
      pathExt: D ? xu.delimiter : void 0
    });
  } catch (e) {} finally {
    if (i) {
      process.chdir(t);
    }
  }
  if (a) {
    a = xu.resolve(n ? e.options.cwd : "", a);
  }
  return a;
}

var Tu = function resolveCommand$1(e) {
  return resolveCommandAttempt(e) || resolveCommandAttempt(e, !0);
};

var Iu = {};

var Ou = /([()\][%!^"`<>&|;, *?])/g;

Iu.command = function escapeCommand(e) {
  return e = e.replace(Ou, "^$1");
};

Iu.argument = function escapeArgument(e, D) {
  e = (e = `"${e = (e = (e = `${e}`).replace(/(\\*)"/g, '$1$1\\"')).replace(/(\\*)$/, "$1$1")}"`).replace(Ou, "^$1");
  if (D) {
    e = e.replace(Ou, "^$1");
  }
  return e;
};

var ku = /^#!(.*)/;

var ju = s;

var shebangCommand = (e = "") => {
  var D = e.match(ku);
  if (!D) {
    return null;
  }
  var [r, t] = D[0].replace(/#! ?/, "").split(" ");
  var n = r.split("/").pop();
  if ("env" === n) {
    return t;
  }
  return t ? `${n} ${t}` : n;
};

var Pu = c;

var Gu = Tu;

var Ru = Iu;

var Lu = function readShebang$1(e) {
  var D = Buffer.alloc(150);
  var r;
  try {
    r = ju.openSync(e, "r");
    ju.readSync(r, D, 0, 150, 0);
    ju.closeSync(r);
  } catch (e) {}
  return shebangCommand(D.toString());
};

var Mu = "win32" === process.platform;

var _u = /\.(?:com|exe)$/i;

var Nu = /node_modules[\\/].bin[\\/][^\\/]+\.cmd$/i;

function parseNonShell(e) {
  if (!Mu) {
    return e;
  }
  var D = function detectShebang(e) {
    e.file = Gu(e);
    var D = e.file && Lu(e.file);
    if (D) {
      e.args.unshift(e.file);
      e.command = D;
      return Gu(e);
    }
    return e.file;
  }(e);
  var r = !_u.test(D);
  if (e.options.forceShell || r) {
    var t = Nu.test(D);
    e.command = Pu.normalize(e.command);
    e.command = Ru.command(e.command);
    e.args = e.args.map((e => Ru.argument(e, t)));
    var n = [ e.command ].concat(e.args).join(" ");
    e.args = [ "/d", "/s", "/c", `"${n}"` ];
    e.command = process.env.comspec || "cmd.exe";
    e.options.windowsVerbatimArguments = !0;
  }
  return e;
}

var Wu = "win32" === process.platform;

function notFoundError(e, D) {
  return Object.assign(new Error(`${D} ${e.command} ENOENT`), {
    code: "ENOENT",
    errno: "ENOENT",
    syscall: `${D} ${e.command}`,
    path: e.command,
    spawnargs: e.args
  });
}

function verifyENOENT(e, D) {
  if (Wu && 1 === e && !D.file) {
    return notFoundError(D.original, "spawn");
  }
  return null;
}

var Uu = {
  hookChildProcess: function hookChildProcess(e, D) {
    if (!Wu) {
      return;
    }
    var r = e.emit;
    e.emit = function(t, n) {
      if ("exit" === t) {
        var i = verifyENOENT(n, D);
        if (i) {
          return r.call(e, "error", i);
        }
      }
      return r.apply(e, arguments);
    };
  },
  verifyENOENT,
  verifyENOENTSync: function verifyENOENTSync(e, D) {
    if (Wu && 1 === e && !D.file) {
      return notFoundError(D.original, "spawnSync");
    }
    return null;
  },
  notFoundError
};

var qu = l;

var zu = function parse$1(e, D, r) {
  if (D && !Array.isArray(D)) {
    r = D;
    D = null;
  }
  var t = {
    command: e,
    args: D = D ? D.slice(0) : [],
    options: r = Object.assign({}, r),
    file: void 0,
    original: {
      command: e,
      args: D
    }
  };
  return r.shell ? t : parseNonShell(t);
};

var Vu = Uu;

function spawn(e, D, r) {
  var t = zu(e, D, r);
  var n = qu.spawn(t.command, t.args, t.options);
  Vu.hookChildProcess(n, t);
  return n;
}

Cu.exports = spawn;

Cu.exports.spawn = spawn;

Cu.exports.sync = function spawnSync(e, D, r) {
  var t = zu(e, D, r);
  var n = qu.spawnSync(t.command, t.args, t.options);
  n.error = n.error || Vu.verifyENOENTSync(n.status, t);
  return n;
};

Cu.exports._parse = zu;

Cu.exports._enoent = Vu;

var Ku = getDefaultExportFromCjs(Cu.exports);

function pathKey(e = {}) {
  var {env: D = process.env, platform: r = process.platform} = e;
  if ("win32" !== r) {
    return "PATH";
  }
  return Object.keys(D).reverse().find((e => "PATH" === e.toUpperCase())) || "Path";
}

var applyPreferLocal = (e, D) => {
  var r;
  while (r !== D) {
    e.push(n.join(D, "node_modules/.bin"));
    r = D;
    D = n.resolve(D, "..");
  }
};

var applyExecPath = (e, D, r) => {
  var t = D instanceof URL ? d.fileURLToPath(D) : D;
  e.push(n.resolve(r, t, ".."));
};

var npmRunPathEnv = ({env: D = e.env, ...r} = {}) => {
  var t = pathKey({
    env: D = {
      ...D
    }
  });
  r.path = D[t];
  D[t] = (({cwd: D = e.cwd(), path: r = e.env[pathKey()], preferLocal: t = !0, execPath: i = e.execPath, addExecPath: a = !0} = {}) => {
    var s = D instanceof URL ? d.fileURLToPath(D) : D;
    var c = n.resolve(s);
    var l = [];
    if (t) {
      applyPreferLocal(l, c);
    }
    if (a) {
      applyExecPath(l, i, c);
    }
    return [ ...l, r ].join(n.delimiter);
  })(r);
  return D;
};

var copyProperty = (e, D, r, t) => {
  if ("length" === r || "prototype" === r) {
    return;
  }
  if ("arguments" === r || "caller" === r) {
    return;
  }
  var n = Object.getOwnPropertyDescriptor(e, r);
  var i = Object.getOwnPropertyDescriptor(D, r);
  if (!canCopyProperty(n, i) && t) {
    return;
  }
  Object.defineProperty(e, r, i);
};

var canCopyProperty = function(e, D) {
  return void 0 === e || e.configurable || e.writable === D.writable && e.enumerable === D.enumerable && e.configurable === D.configurable && (e.writable || e.value === D.value);
};

var wrappedToString = (e, D) => `/* Wrapped ${e}*/\n${D}`;

var Hu = Object.getOwnPropertyDescriptor(Function.prototype, "toString");

var Yu = Object.getOwnPropertyDescriptor(Function.prototype.toString, "name");

function mimicFunction(e, D, {ignoreNonConfigurable: r = !1} = {}) {
  var {name: t} = e;
  for (var n of Reflect.ownKeys(D)) {
    copyProperty(e, D, n, r);
  }
  ((e, D) => {
    var r = Object.getPrototypeOf(D);
    if (r === Object.getPrototypeOf(e)) {
      return;
    }
    Object.setPrototypeOf(e, r);
  })(e, D);
  ((e, D, r) => {
    var t = "" === r ? "" : `with ${r.trim()}() `;
    var n = wrappedToString.bind(null, t, D.toString());
    Object.defineProperty(n, "name", Yu);
    Object.defineProperty(e, "toString", {
      ...Hu,
      value: n
    });
  })(e, D, t);
  return e;
}

var Ju = new WeakMap;

var onetime = (e, D = {}) => {
  if ("function" != typeof e) {
    throw new TypeError("Expected a function");
  }
  var r;
  var t = 0;
  var n = e.displayName || e.name || "<anonymous>";
  var onetime = function(...i) {
    Ju.set(onetime, ++t);
    if (1 === t) {
      r = e.apply(this, i);
      e = null;
    } else if (!0 === D.throw) {
      throw new Error(`Function \`${n}\` can only be called once`);
    }
    return r;
  };
  mimicFunction(onetime, e);
  Ju.set(onetime, t);
  return onetime;
};

onetime.callCount = e => {
  if (!Ju.has(e)) {
    throw new Error(`The given function \`${e.name}\` is not wrapped by the \`onetime\` package`);
  }
  return Ju.get(e);
};

var getRealtimeSignal = (e, D) => ({
  name: `SIGRT${D + 1}`,
  number: Xu + D,
  action: "terminate",
  description: "Application-specific signal (realtime)",
  standard: "posix"
});

var Xu = 34;

var Zu = 64;

var Qu = [ {
  name: "SIGHUP",
  number: 1,
  action: "terminate",
  description: "Terminal closed",
  standard: "posix"
}, {
  name: "SIGINT",
  number: 2,
  action: "terminate",
  description: "User interruption with CTRL-C",
  standard: "ansi"
}, {
  name: "SIGQUIT",
  number: 3,
  action: "core",
  description: "User interruption with CTRL-\\",
  standard: "posix"
}, {
  name: "SIGILL",
  number: 4,
  action: "core",
  description: "Invalid machine instruction",
  standard: "ansi"
}, {
  name: "SIGTRAP",
  number: 5,
  action: "core",
  description: "Debugger breakpoint",
  standard: "posix"
}, {
  name: "SIGABRT",
  number: 6,
  action: "core",
  description: "Aborted",
  standard: "ansi"
}, {
  name: "SIGIOT",
  number: 6,
  action: "core",
  description: "Aborted",
  standard: "bsd"
}, {
  name: "SIGBUS",
  number: 7,
  action: "core",
  description: "Bus error due to misaligned, non-existing address or paging error",
  standard: "bsd"
}, {
  name: "SIGEMT",
  number: 7,
  action: "terminate",
  description: "Command should be emulated but is not implemented",
  standard: "other"
}, {
  name: "SIGFPE",
  number: 8,
  action: "core",
  description: "Floating point arithmetic error",
  standard: "ansi"
}, {
  name: "SIGKILL",
  number: 9,
  action: "terminate",
  description: "Forced termination",
  standard: "posix",
  forced: !0
}, {
  name: "SIGUSR1",
  number: 10,
  action: "terminate",
  description: "Application-specific signal",
  standard: "posix"
}, {
  name: "SIGSEGV",
  number: 11,
  action: "core",
  description: "Segmentation fault",
  standard: "ansi"
}, {
  name: "SIGUSR2",
  number: 12,
  action: "terminate",
  description: "Application-specific signal",
  standard: "posix"
}, {
  name: "SIGPIPE",
  number: 13,
  action: "terminate",
  description: "Broken pipe or socket",
  standard: "posix"
}, {
  name: "SIGALRM",
  number: 14,
  action: "terminate",
  description: "Timeout or timer",
  standard: "posix"
}, {
  name: "SIGTERM",
  number: 15,
  action: "terminate",
  description: "Termination",
  standard: "ansi"
}, {
  name: "SIGSTKFLT",
  number: 16,
  action: "terminate",
  description: "Stack is empty or overflowed",
  standard: "other"
}, {
  name: "SIGCHLD",
  number: 17,
  action: "ignore",
  description: "Child process terminated, paused or unpaused",
  standard: "posix"
}, {
  name: "SIGCLD",
  number: 17,
  action: "ignore",
  description: "Child process terminated, paused or unpaused",
  standard: "other"
}, {
  name: "SIGCONT",
  number: 18,
  action: "unpause",
  description: "Unpaused",
  standard: "posix",
  forced: !0
}, {
  name: "SIGSTOP",
  number: 19,
  action: "pause",
  description: "Paused",
  standard: "posix",
  forced: !0
}, {
  name: "SIGTSTP",
  number: 20,
  action: "pause",
  description: 'Paused using CTRL-Z or "suspend"',
  standard: "posix"
}, {
  name: "SIGTTIN",
  number: 21,
  action: "pause",
  description: "Background process cannot read terminal input",
  standard: "posix"
}, {
  name: "SIGBREAK",
  number: 21,
  action: "terminate",
  description: "User interruption with CTRL-BREAK",
  standard: "other"
}, {
  name: "SIGTTOU",
  number: 22,
  action: "pause",
  description: "Background process cannot write to terminal output",
  standard: "posix"
}, {
  name: "SIGURG",
  number: 23,
  action: "ignore",
  description: "Socket received out-of-band data",
  standard: "bsd"
}, {
  name: "SIGXCPU",
  number: 24,
  action: "core",
  description: "Process timed out",
  standard: "bsd"
}, {
  name: "SIGXFSZ",
  number: 25,
  action: "core",
  description: "File too big",
  standard: "bsd"
}, {
  name: "SIGVTALRM",
  number: 26,
  action: "terminate",
  description: "Timeout or timer",
  standard: "bsd"
}, {
  name: "SIGPROF",
  number: 27,
  action: "terminate",
  description: "Timeout or timer",
  standard: "bsd"
}, {
  name: "SIGWINCH",
  number: 28,
  action: "ignore",
  description: "Terminal window size changed",
  standard: "bsd"
}, {
  name: "SIGIO",
  number: 29,
  action: "terminate",
  description: "I/O is available",
  standard: "other"
}, {
  name: "SIGPOLL",
  number: 29,
  action: "terminate",
  description: "Watched event",
  standard: "other"
}, {
  name: "SIGINFO",
  number: 29,
  action: "ignore",
  description: "Request for process information",
  standard: "other"
}, {
  name: "SIGPWR",
  number: 30,
  action: "terminate",
  description: "Device running out of power",
  standard: "systemv"
}, {
  name: "SIGSYS",
  number: 31,
  action: "core",
  description: "Invalid system call",
  standard: "other"
}, {
  name: "SIGUNUSED",
  number: 31,
  action: "terminate",
  description: "Invalid system call",
  standard: "other"
} ];

var getSignals = () => {
  var e = Array.from({
    length: Zu - Xu + 1
  }, getRealtimeSignal);
  return [ ...Qu, ...e ].map(normalizeSignal);
};

var normalizeSignal = ({name: e, number: D, description: r, action: t, forced: n = !1, standard: i}) => {
  var {signals: {[e]: a}} = p.constants;
  var s = void 0 !== a;
  return {
    name: e,
    number: s ? a : D,
    description: r,
    supported: s,
    action: t,
    forced: n,
    standard: i
  };
};

var getSignalByName = ({name: e, number: D, description: r, supported: t, action: n, forced: i, standard: a}) => [ e, {
  name: e,
  number: D,
  description: r,
  supported: t,
  action: n,
  forced: i,
  standard: a
} ];

var ee = (() => {
  var e = getSignals();
  return Object.fromEntries(e.map(getSignalByName));
})();

var getSignalByNumber = (e, D) => {
  var r = findSignalByNumber(e, D);
  if (void 0 === r) {
    return {};
  }
  var {name: t, description: n, supported: i, action: a, forced: s, standard: c} = r;
  return {
    [e]: {
      name: t,
      number: e,
      description: n,
      supported: i,
      action: a,
      forced: s,
      standard: c
    }
  };
};

var findSignalByNumber = (e, D) => {
  var r = D.find((({name: D}) => p.constants.signals[D] === e));
  if (void 0 !== r) {
    return r;
  }
  return D.find((D => D.number === e));
};

(() => {
  var e = getSignals();
  var D = Array.from({
    length: Zu + 1
  }, ((D, r) => getSignalByNumber(r, e)));
  Object.assign({}, ...D);
})();

var makeError = ({stdout: D, stderr: r, all: t, error: n, signal: i, exitCode: a, command: s, escapedCommand: c, timedOut: l, isCanceled: d, killed: p, parsed: {options: {timeout: E, cwd: f = e.cwd()}}}) => {
  var h = void 0 === (i = null === i ? void 0 : i) ? void 0 : ee[i].description;
  var m = (({timedOut: e, timeout: D, errorCode: r, signal: t, signalDescription: n, exitCode: i, isCanceled: a}) => {
    if (e) {
      return `timed out after ${D} milliseconds`;
    }
    if (a) {
      return "was canceled";
    }
    if (void 0 !== r) {
      return `failed with ${r}`;
    }
    if (void 0 !== t) {
      return `was killed with ${t} (${n})`;
    }
    if (void 0 !== i) {
      return `failed with exit code ${i}`;
    }
    return "failed";
  })({
    timedOut: l,
    timeout: E,
    errorCode: n && n.code,
    signal: i,
    signalDescription: h,
    exitCode: a = null === a ? void 0 : a,
    isCanceled: d
  });
  var g = `Command ${m}: ${s}`;
  var B = "[object Error]" === Object.prototype.toString.call(n);
  var b = B ? `${g}\n${n.message}` : g;
  var w = [ b, r, D ].filter(Boolean).join("\n");
  if (B) {
    n.originalMessage = n.message;
    n.message = w;
  } else {
    n = new Error(w);
  }
  n.shortMessage = b;
  n.command = s;
  n.escapedCommand = c;
  n.exitCode = a;
  n.signal = i;
  n.signalDescription = h;
  n.stdout = D;
  n.stderr = r;
  n.cwd = f;
  if (void 0 !== t) {
    n.all = t;
  }
  if ("bufferedData" in n) {
    delete n.bufferedData;
  }
  n.failed = !0;
  n.timedOut = Boolean(l);
  n.isCanceled = d;
  n.killed = p && !l;
  return n;
};

var De = [ "stdin", "stdout", "stderr" ];

var normalizeStdio = e => {
  if (!e) {
    return;
  }
  var {stdio: D} = e;
  if (void 0 === D) {
    return De.map((D => e[D]));
  }
  if ((e => De.some((D => void 0 !== e[D])))(e)) {
    throw new Error(`It's not possible to provide \`stdio\` in combination with one of ${De.map((e => `\`${e}\``)).join(", ")}`);
  }
  if ("string" == typeof D) {
    return D;
  }
  if (!Array.isArray(D)) {
    throw new TypeError(`Expected \`stdio\` to be of type \`string\` or \`Array\`, got \`${typeof D}\``);
  }
  var r = Math.max(D.length, De.length);
  return Array.from({
    length: r
  }, ((e, r) => D[r]));
};

var re = [];

re.push("SIGHUP", "SIGINT", "SIGTERM");

if ("win32" !== process.platform) {
  re.push("SIGALRM", "SIGABRT", "SIGVTALRM", "SIGXCPU", "SIGXFSZ", "SIGUSR2", "SIGTRAP", "SIGSYS", "SIGQUIT", "SIGIOT");
}

if ("linux" === process.platform) {
  re.push("SIGIO", "SIGPOLL", "SIGPWR", "SIGSTKFLT");
}

var processOk = e => !!e && "object" == typeof e && "function" == typeof e.removeListener && "function" == typeof e.emit && "function" == typeof e.reallyExit && "function" == typeof e.listeners && "function" == typeof e.kill && "number" == typeof e.pid && "function" == typeof e.on;

var ne = Symbol.for("signal-exit emitter");

var ie = globalThis;

var ae = Object.defineProperty.bind(Object);

class Emitter {
  emitted={
    afterExit: !1,
    exit: !1
  };
  listeners={
    afterExit: [],
    exit: []
  };
  count=0;
  id=Math.random();
  constructor() {
    if (ie[ne]) {
      return ie[ne];
    }
    ae(ie, ne, {
      value: this,
      writable: !1,
      enumerable: !1,
      configurable: !1
    });
  }
  on(e, D) {
    this.listeners[e].push(D);
  }
  removeListener(e, D) {
    var r = this.listeners[e];
    var t = r.indexOf(D);
    if (-1 === t) {
      return;
    }
    if (0 === t && 1 === r.length) {
      r.length = 0;
    } else {
      r.splice(t, 1);
    }
  }
  emit(e, D, r) {
    if (this.emitted[e]) {
      return !1;
    }
    this.emitted[e] = !0;
    var t = !1;
    for (var n of this.listeners[e]) {
      t = !0 === n(D, r) || t;
    }
    if ("exit" === e) {
      t = this.emit("afterExit", D, r) || t;
    }
    return t;
  }
}

class SignalExitBase {}

var oe = globalThis.process;

var {onExit: ce} = (Fe = processOk(oe) ? new class SignalExit extends SignalExitBase {
  #u="win32" === oe.platform ? "SIGINT" : "SIGHUP";
  #e=new Emitter;
  #D;
  #r;
  #t;
  #n={};
  #i=!1;
  constructor(e) {
    var D;
    super();
    D = this;
    this.#D = e;
    this.#n = {};
    var _loop = function(r) {
      D.#n[r] = () => {
        var t = D.#D.listeners(r);
        var {count: n} = D.#e;
        if ("object" == typeof e.__signal_exit_emitter__ && "number" == typeof e.__signal_exit_emitter__.count) {
          n += e.__signal_exit_emitter__.count;
        }
        if (t.length === n) {
          D.unload();
          var i = D.#e.emit("exit", null, r);
          var a = "SIGHUP" === r ? D.#u : r;
          if (!i) {
            e.kill(e.pid, a);
          }
        }
      };
    };
    for (var r of re) {
      _loop(r);
    }
    this.#t = e.reallyExit;
    this.#r = e.emit;
  }
  onExit(e, D) {
    if (!processOk(this.#D)) {
      return () => {};
    }
    if (!1 === this.#i) {
      this.load();
    }
    var r = D?.alwaysLast ? "afterExit" : "exit";
    this.#e.on(r, e);
    return () => {
      this.#e.removeListener(r, e);
      if (0 === this.#e.listeners.exit.length && 0 === this.#e.listeners.afterExit.length) {
        this.unload();
      }
    };
  }
  load() {
    if (this.#i) {
      return;
    }
    this.#i = !0;
    this.#e.count += 1;
    for (var e of re) {
      try {
        var D = this.#n[e];
        if (D) {
          this.#D.on(e, D);
        }
      } catch (e) {}
    }
    this.#D.emit = (e, ...D) => this.#a(e, ...D);
    this.#D.reallyExit = e => this.#s(e);
  }
  unload() {
    if (!this.#i) {
      return;
    }
    this.#i = !1;
    re.forEach((e => {
      var D = this.#n[e];
      if (!D) {
        throw new Error("Listener not defined for signal: " + e);
      }
      try {
        this.#D.removeListener(e, D);
      } catch (e) {}
    }));
    this.#D.emit = this.#r;
    this.#D.reallyExit = this.#t;
    this.#e.count -= 1;
  }
  #s(e) {
    if (!processOk(this.#D)) {
      return 0;
    }
    this.#D.exitCode = e || 0;
    this.#e.emit("exit", this.#D.exitCode, null);
    return this.#t.call(this.#D, this.#D.exitCode);
  }
  #a(e, ...D) {
    var r = this.#r;
    if ("exit" === e && processOk(this.#D)) {
      if ("number" == typeof D[0]) {
        this.#D.exitCode = D[0];
      }
      var t = r.call(this.#D, e, ...D);
      this.#e.emit("exit", this.#D.exitCode, null);
      return t;
    } else {
      return r.call(this.#D, e, ...D);
    }
  }
}(oe) : new class SignalExitFallback extends SignalExitBase {
  onExit() {
    return () => {};
  }
  load() {}
  unload() {}
}, {
  onExit: (e, D) => Fe.onExit(e, D),
  load: () => Fe.load(),
  unload: () => Fe.unload()
});

var Fe;

var spawnedKill = (e, D = "SIGTERM", r = {}) => {
  var t = e(D);
  setKillTimeout(e, D, r, t);
  return t;
};

var setKillTimeout = (e, D, r, t) => {
  if (!shouldForceKill(D, r, t)) {
    return;
  }
  var n = getForceKillAfterTimeout(r);
  var i = setTimeout((() => {
    e("SIGKILL");
  }), n);
  if (i.unref) {
    i.unref();
  }
};

var shouldForceKill = (e, {forceKillAfterTimeout: D}, r) => isSigterm(e) && !1 !== D && r;

var isSigterm = e => e === p.constants.signals.SIGTERM || "string" == typeof e && "SIGTERM" === e.toUpperCase();

var getForceKillAfterTimeout = ({forceKillAfterTimeout: e = !0}) => {
  if (!0 === e) {
    return 5e3;
  }
  if (!Number.isFinite(e) || e < 0) {
    throw new TypeError(`Expected the \`forceKillAfterTimeout\` option to be a non-negative integer, got \`${e}\` (${typeof e})`);
  }
  return e;
};

var spawnedCancel = (e, D) => {
  if (e.kill()) {
    D.isCanceled = !0;
  }
};

var setupTimeout = (e, {timeout: D, killSignal: r = "SIGTERM"}, t) => {
  if (0 === D || void 0 === D) {
    return t;
  }
  var n;
  var i = new Promise(((t, i) => {
    n = setTimeout((() => {
      ((e, D, r) => {
        e.kill(D);
        r(Object.assign(new Error("Timed out"), {
          timedOut: !0,
          signal: D
        }));
      })(e, r, i);
    }), D);
  }));
  var a = t.finally((() => {
    clearTimeout(n);
  }));
  return Promise.race([ i, a ]);
};

var validateTimeout = ({timeout: e}) => {
  if (void 0 !== e && (!Number.isFinite(e) || e < 0)) {
    throw new TypeError(`Expected the \`timeout\` option to be a non-negative integer, got \`${e}\` (${typeof e})`);
  }
};

var setExitHandler = async (e, {cleanup: D, detached: r}, t) => {
  if (!D || r) {
    return t;
  }
  var n = ce((() => {
    e.kill();
  }));
  return t.finally((() => {
    n();
  }));
};

function isStream(e) {
  return null !== e && "object" == typeof e && "function" == typeof e.pipe;
}

function isWritableStream(e) {
  return isStream(e) && !1 !== e.writable && "function" == typeof e._write && "object" == typeof e._writableState;
}

var pipeToTarget = (e, D, r) => {
  if ("string" == typeof r) {
    e[D].pipe(E.createWriteStream(r));
    return e;
  }
  if (isWritableStream(r)) {
    e[D].pipe(r);
    return e;
  }
  if (!(e => e instanceof a.ChildProcess && "function" == typeof e.then)(r)) {
    throw new TypeError("The second argument must be a string, a stream or an Execa child process.");
  }
  if (!isWritableStream(r.stdin)) {
    throw new TypeError("The target child process's stdin must be available.");
  }
  e[D].pipe(r.stdin);
  return r;
};

var addPipeMethods = e => {
  if (null !== e.stdout) {
    e.pipeStdout = pipeToTarget.bind(void 0, e, "stdout");
  }
  if (null !== e.stderr) {
    e.pipeStderr = pipeToTarget.bind(void 0, e, "stderr");
  }
  if (void 0 !== e.all) {
    e.pipeAll = pipeToTarget.bind(void 0, e, "all");
  }
};

var getStreamContents = async (e, {init: D, convertChunk: r, getSize: t, truncateChunk: n, addChunk: i, getFinalChunk: a, finalize: s}, {maxBuffer: c = Number.POSITIVE_INFINITY} = {}) => {
  if (!isAsyncIterable(e)) {
    throw new Error("The first argument must be a Readable, a ReadableStream, or an async iterable.");
  }
  var l = D();
  l.length = 0;
  try {
    for await (var d of e) {
      var p = r[getChunkType(d)](d, l);
      appendChunk({
        convertedChunk: p,
        state: l,
        getSize: t,
        truncateChunk: n,
        addChunk: i,
        maxBuffer: c
      });
    }
    appendFinalChunk({
      state: l,
      convertChunk: r,
      getSize: t,
      truncateChunk: n,
      addChunk: i,
      getFinalChunk: a,
      maxBuffer: c
    });
    return s(l);
  } catch (e) {
    e.bufferedData = s(l);
    throw e;
  }
};

var appendFinalChunk = ({state: e, getSize: D, truncateChunk: r, addChunk: t, getFinalChunk: n, maxBuffer: i}) => {
  var a = n(e);
  if (void 0 !== a) {
    appendChunk({
      convertedChunk: a,
      state: e,
      getSize: D,
      truncateChunk: r,
      addChunk: t,
      maxBuffer: i
    });
  }
};

var appendChunk = ({convertedChunk: e, state: D, getSize: r, truncateChunk: t, addChunk: n, maxBuffer: i}) => {
  var a = r(e);
  var s = D.length + a;
  if (s <= i) {
    addNewChunk(e, D, n, s);
    return;
  }
  var c = t(e, i - D.length);
  if (void 0 !== c) {
    addNewChunk(c, D, n, i);
  }
  throw new MaxBufferError;
};

var addNewChunk = (e, D, r, t) => {
  D.contents = r(e, D, t);
  D.length = t;
};

var isAsyncIterable = e => "object" == typeof e && null !== e && "function" == typeof e[Symbol.asyncIterator];

var getChunkType = e => {
  var D = typeof e;
  if ("string" === D) {
    return "string";
  }
  if ("object" !== D || null === e) {
    return "others";
  }
  if (globalThis.Buffer?.isBuffer(e)) {
    return "buffer";
  }
  var r = le.call(e);
  if ("[object ArrayBuffer]" === r) {
    return "arrayBuffer";
  }
  if ("[object DataView]" === r) {
    return "dataView";
  }
  if (Number.isInteger(e.byteLength) && Number.isInteger(e.byteOffset) && "[object ArrayBuffer]" === le.call(e.buffer)) {
    return "typedArray";
  }
  return "others";
};

var {toString: le} = Object.prototype;

class MaxBufferError extends Error {
  name="MaxBufferError";
  constructor() {
    super("maxBuffer exceeded");
  }
}

var throwObjectStream = e => {
  throw new Error(`Streams in object mode are not supported: ${String(e)}`);
};

var getLengthProp = e => e.length;

var Ce = new TextEncoder;

var useUint8Array = e => new Uint8Array(e);

var useUint8ArrayWithOffset = e => new Uint8Array(e.buffer, e.byteOffset, e.byteLength);

var resizeArrayBufferSlow = (e, D) => {
  if (D <= e.byteLength) {
    return e;
  }
  var r = new ArrayBuffer(getNewContentsLength(D));
  new Uint8Array(r).set(new Uint8Array(e), 0);
  return r;
};

var resizeArrayBuffer = (e, D) => {
  if (D <= e.maxByteLength) {
    e.resize(D);
    return e;
  }
  var r = new ArrayBuffer(D, {
    maxByteLength: getNewContentsLength(D)
  });
  new Uint8Array(r).set(new Uint8Array(e), 0);
  return r;
};

var getNewContentsLength = e => pe ** Math.ceil(Math.log(e) / Math.log(pe));

var pe = 2;

var hasArrayBufferResize = () => "resize" in ArrayBuffer.prototype;

var Ee = {
  init: () => ({
    contents: new ArrayBuffer(0)
  }),
  convertChunk: {
    string: e => Ce.encode(e),
    buffer: useUint8Array,
    arrayBuffer: useUint8Array,
    dataView: useUint8ArrayWithOffset,
    typedArray: useUint8ArrayWithOffset,
    others: throwObjectStream
  },
  getSize: getLengthProp,
  truncateChunk: (e, D) => e.slice(0, D),
  addChunk: (e, {contents: D, length: r}, t) => {
    var n = hasArrayBufferResize() ? resizeArrayBuffer(D, t) : resizeArrayBufferSlow(D, t);
    new Uint8Array(n).set(e, r);
    return n;
  },
  getFinalChunk: () => {},
  finalize: ({contents: e, length: D}) => hasArrayBufferResize() ? e : e.slice(0, D)
};

async function getStreamAsBuffer(e, D) {
  if (!("Buffer" in globalThis)) {
    throw new Error("getStreamAsBuffer() is only supported in Node.js");
  }
  try {
    return arrayBufferToNodeBuffer(await async function getStreamAsArrayBuffer(e, D) {
      return getStreamContents(e, Ee, D);
    }(e, D));
  } catch (e) {
    if (void 0 !== e.bufferedData) {
      e.bufferedData = arrayBufferToNodeBuffer(e.bufferedData);
    }
    throw e;
  }
}

var arrayBufferToNodeBuffer = e => globalThis.Buffer.from(e);

var useTextDecoder = (e, {textDecoder: D}) => D.decode(e, {
  stream: !0
});

var fe = {
  init: () => ({
    contents: "",
    textDecoder: new TextDecoder
  }),
  convertChunk: {
    string: e => e,
    buffer: useTextDecoder,
    arrayBuffer: useTextDecoder,
    dataView: useTextDecoder,
    typedArray: useTextDecoder,
    others: throwObjectStream
  },
  getSize: getLengthProp,
  truncateChunk: (e, D) => e.slice(0, D),
  addChunk: (e, {contents: D}) => D + e,
  getFinalChunk: ({textDecoder: e}) => {
    var D = e.decode();
    return "" === D ? void 0 : D;
  },
  finalize: ({contents: e}) => e
};

var {PassThrough: ve} = h;

var he = getDefaultExportFromCjs((function() {
  var e = [];
  var D = new ve({
    objectMode: !0
  });
  D.setMaxListeners(0);
  D.add = add;
  D.isEmpty = function isEmpty() {
    return 0 == e.length;
  };
  D.on("unpipe", remove);
  Array.prototype.slice.call(arguments).forEach(add);
  return D;
  function add(r) {
    if (Array.isArray(r)) {
      r.forEach(add);
      return this;
    }
    e.push(r);
    r.once("end", remove.bind(null, r));
    r.once("error", D.emit.bind(D, "error"));
    r.pipe(D, {
      end: !1
    });
    return this;
  }
  function remove(r) {
    if (!(e = e.filter((function(e) {
      return e !== r;
    }))).length && D.readable) {
      D.end();
    }
  }
}));

var getInput = ({input: e, inputFile: D}) => {
  if ("string" != typeof D) {
    return e;
  }
  (e => {
    if (void 0 !== e) {
      throw new TypeError("The `input` and `inputFile` options cannot be both set.");
    }
  })(e);
  return E.createReadStream(D);
};

var handleInput = (e, D) => {
  var r = getInput(D);
  if (void 0 === r) {
    return;
  }
  if (isStream(r)) {
    r.pipe(e.stdin);
  } else {
    e.stdin.end(r);
  }
};

var makeAllStream = (e, {all: D}) => {
  if (!D || !e.stdout && !e.stderr) {
    return;
  }
  var r = he();
  if (e.stdout) {
    r.add(e.stdout);
  }
  if (e.stderr) {
    r.add(e.stderr);
  }
  return r;
};

var getBufferedData = async (e, D) => {
  if (!e || void 0 === D) {
    return;
  }
  await f.setTimeout(0);
  e.destroy();
  try {
    return await D;
  } catch (e) {
    return e.bufferedData;
  }
};

var getStreamPromise = (e, {encoding: D, buffer: r, maxBuffer: t}) => {
  if (!e || !r) {
    return;
  }
  if ("utf8" === D || "utf-8" === D) {
    return async function getStreamAsString(e, D) {
      return getStreamContents(e, fe, D);
    }(e, {
      maxBuffer: t
    });
  }
  if (null === D || "buffer" === D) {
    return getStreamAsBuffer(e, {
      maxBuffer: t
    });
  }
  return applyEncoding(e, t, D);
};

var applyEncoding = async (e, D, r) => (await getStreamAsBuffer(e, {
  maxBuffer: D
})).toString(r);

var getSpawnedResult = async ({stdout: e, stderr: D, all: r}, {encoding: t, buffer: n, maxBuffer: i}, a) => {
  var s = getStreamPromise(e, {
    encoding: t,
    buffer: n,
    maxBuffer: i
  });
  var c = getStreamPromise(D, {
    encoding: t,
    buffer: n,
    maxBuffer: i
  });
  var l = getStreamPromise(r, {
    encoding: t,
    buffer: n,
    maxBuffer: 2 * i
  });
  try {
    return await Promise.all([ a, s, c, l ]);
  } catch (t) {
    return Promise.all([ {
      error: t,
      signal: t.signal,
      timedOut: t.timedOut
    }, getBufferedData(e, s), getBufferedData(D, c), getBufferedData(r, l) ]);
  }
};

var me = (async () => {})().constructor.prototype;

var ge = [ "then", "catch", "finally" ].map((e => [ e, Reflect.getOwnPropertyDescriptor(me, e) ]));

var mergePromise = (e, D) => {
  var _loop = function(t) {
    var n = "function" == typeof D ? (...e) => Reflect.apply(t.value, D(), e) : t.value.bind(D);
    Reflect.defineProperty(e, r, {
      ...t,
      value: n
    });
  };
  for (var [r, t] of ge) {
    _loop(t);
  }
};

var getSpawnedPromise = e => new Promise(((D, r) => {
  e.on("exit", ((e, r) => {
    D({
      exitCode: e,
      signal: r
    });
  }));
  e.on("error", (e => {
    r(e);
  }));
  if (e.stdin) {
    e.stdin.on("error", (e => {
      r(e);
    }));
  }
}));

var normalizeArgs = (e, D = []) => {
  if (!Array.isArray(D)) {
    return [ e ];
  }
  return [ e, ...D ];
};

var Be = /^[\w.-]+$/;

var joinCommand = (e, D) => normalizeArgs(e, D).join(" ");

var getEscapedCommand = (e, D) => normalizeArgs(e, D).map((e => (e => {
  if ("string" != typeof e || Be.test(e)) {
    return e;
  }
  return `"${e.replaceAll('"', '\\"')}"`;
})(e))).join(" ");

var be = m.debuglog("execa").enabled;

var padField = (e, D) => String(e).padStart(D, "0");

var logCommand = (D, {verbose: r}) => {
  if (!r) {
    return;
  }
  e.stderr.write(`[${t = new Date, `${padField(t.getHours(), 2)}:${padField(t.getMinutes(), 2)}:${padField(t.getSeconds(), 2)}.${padField(t.getMilliseconds(), 3)}`}] ${D}\n`);
  var t;
};

var handleArguments = (D, r, t = {}) => {
  var i = Ku._parse(D, r, t);
  D = i.command;
  r = i.args;
  (t = {
    maxBuffer: 1e8,
    buffer: !0,
    stripFinalNewline: !0,
    extendEnv: !0,
    preferLocal: !1,
    localDir: (t = i.options).cwd || e.cwd(),
    execPath: e.execPath,
    encoding: "utf8",
    reject: !0,
    cleanup: !0,
    all: !1,
    windowsHide: !0,
    verbose: be,
    ...t
  }).env = (({env: D, extendEnv: r, preferLocal: t, localDir: n, execPath: i}) => {
    var a = r ? {
      ...e.env,
      ...D
    } : D;
    if (t) {
      return npmRunPathEnv({
        env: a,
        cwd: n,
        execPath: i
      });
    }
    return a;
  })(t);
  t.stdio = normalizeStdio(t);
  if ("win32" === e.platform && "cmd" === n.basename(D, ".exe")) {
    r.unshift("/q");
  }
  return {
    file: D,
    args: r,
    options: t,
    parsed: i
  };
};

var handleOutput = (e, D, r) => {
  if ("string" != typeof D && !i.Buffer.isBuffer(D)) {
    return void 0 === r ? void 0 : "";
  }
  if (e.stripFinalNewline) {
    return function stripFinalNewline(e) {
      var D = "string" == typeof e ? "\n" : "\n".charCodeAt();
      var r = "string" == typeof e ? "\r" : "\r".charCodeAt();
      if (e[e.length - 1] === D) {
        e = e.slice(0, -1);
      }
      if (e[e.length - 1] === r) {
        e = e.slice(0, -1);
      }
      return e;
    }(D);
  }
  return D;
};

function execa(e, D, r) {
  var t = handleArguments(e, D, r);
  var n = joinCommand(e, D);
  var i = getEscapedCommand(e, D);
  logCommand(i, t.options);
  validateTimeout(t.options);
  var s;
  try {
    s = a.spawn(t.file, t.args, t.options);
  } catch (e) {
    var c = new a.ChildProcess;
    var l = Promise.reject(makeError({
      error: e,
      stdout: "",
      stderr: "",
      all: "",
      command: n,
      escapedCommand: i,
      parsed: t,
      timedOut: !1,
      isCanceled: !1,
      killed: !1
    }));
    mergePromise(c, l);
    return c;
  }
  var d = getSpawnedPromise(s);
  var p = setupTimeout(s, t.options, d);
  var E = setExitHandler(s, t.options, p);
  s.kill = spawnedKill.bind(null, s.kill.bind(s));
  s.cancel = spawnedCancel.bind(null, s, {
    isCanceled: !1
  });
  var f = onetime((async () => {
    var [{error: e, exitCode: D, signal: r, timedOut: a}, c, l, d] = await getSpawnedResult(s, t.options, E);
    var p = handleOutput(t.options, c);
    var f = handleOutput(t.options, l);
    var h = handleOutput(t.options, d);
    if (e || 0 !== D || null !== r) {
      var m = makeError({
        error: e,
        exitCode: D,
        signal: r,
        stdout: p,
        stderr: f,
        all: h,
        command: n,
        escapedCommand: i,
        parsed: t,
        timedOut: a,
        isCanceled: t.options.signal ? t.options.signal.aborted : !1,
        killed: s.killed
      });
      if (!t.options.reject) {
        return m;
      }
      throw m;
    }
    return {
      command: n,
      escapedCommand: i,
      exitCode: 0,
      stdout: p,
      stderr: f,
      all: h,
      failed: !1,
      timedOut: !1,
      isCanceled: !1,
      killed: !1
    };
  }));
  handleInput(s, t.options);
  s.all = makeAllStream(s, t.options);
  addPipeMethods(s);
  mergePromise(s, f);
  return s;
}

var question = async (e, D, r) => {
  var t = "";
  var n = !1;
  while (!n) {
    if (hD(t = await te({
      message: e
    }))) {
      n = !0;
      ue("Operation cancelled.");
      process.exit(0);
    } else if (await D(t)) {
      n = !0;
    }
  }
  return t;
};

exports.run = async function run(e) {
  var D = de();
  ((e = "") => {
    process.stdout.write(`${_.gray(ou)}  ${e}\n`);
  })("GQL.Tada");
  var r = await question("Where can we get your schema? Point us at an introspection JSON-file, a GraphQL schema file or an endpoint", (async r => {
    try {
      var i = new URL(r);
      D.start("Validating the URL.");
      try {
        var a = await fetch(i.toString());
        if (!a.ok) {
          D.stop("Validated the URL.");
          return !!await se({
            message: `Got ${a.status} from ${i.toString()}, continue anyway? You can add headers later.`
          });
        }
      } catch (e) {
        D.stop("Validated the URL.");
        return !!await se({
          message: `Got ${e.message} from ${i.toString()}, continue anyway? You can add headers later.`
        });
      }
      D.stop("Validated the URL.");
      return !0;
    } catch (e) {}
    if (!(r.endsWith(".json") || r.endsWith(".graphql"))) {
      return !1;
    }
    var s = n.resolve(e, r);
    var c = !!await t.readFile(s);
    if (!c) {
      console.log(`\nCould not find "${s}"`);
    }
    return c;
  }));
  var i = await question("What directory do you want us to write the tadaOutputFile to?", (async D => {
    var r = n.resolve(e, D);
    var i = !!await t.stat(r);
    if (!i) {
      console.log(`\nCould not find "${r}"`);
    }
    return i;
  }));
  if (hD(i)) {
    ue("Operation cancelled.");
    process.exit(0);
  }
  i = n.resolve(i, "graphql-env.d.ts");
  var a = await se({
    message: "Do you want us to install the dependencies?"
  });
  if (hD(a)) {
    ue("Operation cancelled.");
    process.exit(0);
  }
  var s = !1;
  var c;
  try {
    var l = n.resolve(e, "package.json");
    var d = await t.readFile(l, "utf-8");
    c = JSON.parse(d);
    var p = Object.entries({
      ...c.dependencies,
      ...c.devDependencies
    }).find((e => "typescript" === e[0]));
    if (p && "string" == typeof p[1]) {
      s = g.semverComply(p[1], g.MINIMUM_VERSIONS.typescript_embed_lsp);
    }
  } catch (e) {}
  if (a) {
    D.start("Installing packages.");
    await async function installPackages(e, D, r) {
      if (r) {
        await execa(e, [ "yarn" === e ? "add" : "install", "-D", "@0no-co/graphqlsp" ], {
          stdio: "ignore",
          cwd: D
        });
      }
      await execa(e, [ "yarn" === e ? "add" : "install", "gql.tada" ], {
        stdio: "ignore",
        cwd: D
      });
    }(function getPkgManager() {
      var e = process.env.npm_config_user_agent || "";
      if (e.startsWith("yarn")) {
        return "yarn";
      }
      if (e.startsWith("pnpm")) {
        return "pnpm";
      }
      return "npm";
    }(), e, !s);
    D.stop("Installed packages.");
  } else {
    D.start("Writing to package.json.");
    try {
      var E = n.resolve(e, "package.json");
      var f = await t.readFile(E, "utf-8");
      if (!(c = JSON.parse(f)).dependencies) {
        c.dependencies = {};
      }
      if (!c.dependencies["gql.tada"]) {
        c.dependencies["gql.tada"] = "^1.4.3";
      }
      if (!s) {
        if (!c.devDependencies) {
          c.devDependencies = {};
        }
        if (!c.devDependencies["@0no-co/graphqlsp"]) {
          c.devDependencies["@0no-co/graphqlsp"] = "^1.8.0";
        }
      }
      await t.writeFile(E, JSON.stringify(c, null, 2));
      D.stop("Written to package.json.");
    } catch (e) {
      D.stop('Failed to write to package.json, you can try adding "gql.tada" and "@0no-co/graphqlsp" yourself.');
    }
  }
  D.start("Writing to tsconfig.json.");
  var h = "tsconfig.json";
  try {
    var m = n.resolve(e, "tsconfig.json");
    var b = await B.readTSConfigFile(m);
    if (Array.isArray(b.references) && Array.isArray(b.files) && !b.files.length && !b.include) {
      var w;
      var S;
      for (var I of b.references) {
        if (!I || "string" != typeof I.path) {
          continue;
        }
        var O = n.resolve(e, I.path);
        if (".json" !== n.extname(O)) {
          O = n.join(O, "tsconfig.json");
        }
        try {
          await t.access(O);
        } catch (e) {
          continue;
        }
        if ("tsconfig.app.json" === n.basename(O)) {
          S = O;
          break;
        } else if (!w) {
          w = O;
        }
      }
      var k = S || w;
      if (k) {
        m = k;
        b = await B.readTSConfigFile(m);
        h = n.relative(e, m);
      }
    }
    var G = r.endsWith(".json") || r.endsWith(".graphql");
    var M = n.dirname(m);
    b.compilerOptions = {
      ...b.compilerOptions,
      plugins: [ {
        name: s ? "gql.tada/ts-plugin" : "@0no-co/graphqlsp",
        schema: G ? n.relative(M, n.resolve(e, r)) : r,
        tadaOutputLocation: n.relative(M, i)
      } ]
    };
    await t.writeFile(m, JSON.stringify(b, null, 2));
  } catch (e) {}
  D.stop(`Written to ${h}.`);
  ((e = "") => {
    process.stdout.write(`${_.gray(cu)}\n${_.gray(Fu)}  ${e}\n\n`);
  })("Off to the races!");
};
//# sourceMappingURL=runner-chunk.js.map
