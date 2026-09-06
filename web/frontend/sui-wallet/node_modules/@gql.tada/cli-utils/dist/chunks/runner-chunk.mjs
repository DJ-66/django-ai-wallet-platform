import D, { stdin as e, stdout as r } from "node:process";

import * as t from "node:readline";

import n from "node:readline";

import { WriteStream as i } from "node:tty";

import a from "node:fs/promises";

import s from "node:path";

import { Buffer as c } from "node:buffer";

import l, { ChildProcess as d } from "node:child_process";

import p from "fs";

import E from "path";

import f from "child_process";

import { fileURLToPath as h } from "node:url";

import m, { constants as g } from "node:os";

import { createWriteStream as B, createReadStream as b } from "node:fs";

import { setTimeout as w } from "node:timers/promises";

import S from "stream";

import { debuglog as I } from "node:util";

import { s as k, M as O } from "./index-chunk.mjs";

import { readTSConfigFile as G } from "@gql.tada/internal";

function getDefaultExportFromCjs(D) {
  return D && D.__esModule && Object.prototype.hasOwnProperty.call(D, "default") ? D.default : D;
}

var M = "[";

var _ = {
  to(D, e) {
    if (!e) {
      return `${M}${D + 1}G`;
    }
    return `${M}${e + 1};${D + 1}H`;
  },
  move(D, e) {
    var r = "";
    if (D < 0) {
      r += `${M}${-D}D`;
    } else if (D > 0) {
      r += `${M}${D}C`;
    }
    if (e < 0) {
      r += `${M}${-e}A`;
    } else if (e > 0) {
      r += `${M}${e}B`;
    }
    return r;
  },
  up: (D = 1) => `${M}${D}A`,
  down: (D = 1) => `${M}${D}B`,
  forward: (D = 1) => `${M}${D}C`,
  backward: (D = 1) => `${M}${D}D`,
  nextLine: (D = 1) => `${M}E`.repeat(D),
  prevLine: (D = 1) => `${M}F`.repeat(D),
  left: `${M}G`,
  hide: `${M}?25l`,
  show: `${M}?25h`,
  save: "7",
  restore: "8"
};

var U = {
  up: (D = 1) => `${M}S`.repeat(D),
  down: (D = 1) => `${M}T`.repeat(D)
};

var z = {
  screen: `${M}2J`,
  up: (D = 1) => `${M}1J`.repeat(D),
  down: (D = 1) => `${M}J`.repeat(D),
  line: `${M}2K`,
  lineEnd: `${M}K`,
  lineStart: `${M}1K`,
  lines(D) {
    var e = "";
    for (var r = 0; r < D; r++) {
      e += this.line + (r < D - 1 ? _.up() : "");
    }
    if (D) {
      e += _.left;
    }
    return e;
  }
};

var K = {
  cursor: _,
  scroll: U,
  erase: z,
  beep: ""
};

var V = {
  exports: {}
};

var H = String;

var create = function() {
  return {
    isColorSupported: !1,
    reset: H,
    bold: H,
    dim: H,
    italic: H,
    underline: H,
    inverse: H,
    hidden: H,
    strikethrough: H,
    black: H,
    red: H,
    green: H,
    yellow: H,
    blue: H,
    magenta: H,
    cyan: H,
    white: H,
    gray: H,
    bgBlack: H,
    bgRed: H,
    bgGreen: H,
    bgYellow: H,
    bgBlue: H,
    bgMagenta: H,
    bgCyan: H,
    bgWhite: H
  };
};

V.exports = create();

V.exports.createColors = create;

var Y = getDefaultExportFromCjs(V.exports);

function S$1(D) {
  if ("string" != typeof D) {
    throw new TypeError(`Expected a \`string\`, got \`${typeof D}\``);
  }
  return D.replace(function q$1({onlyFirst: D = !1} = {}) {
    var e = [ "[\\u001B\\u009B][[\\]()#;?]*(?:(?:(?:(?:;[-a-zA-Z\\d\\/#&.:=?%@~_]+)*|[a-zA-Z\\d]+(?:;[-a-zA-Z\\d\\/#&.:=?%@~_]*)*)?\\u0007)", "(?:(?:\\d{1,4}(?:;\\d{0,4})*)?[\\dA-PR-TZcf-ntqry=><~]))" ].join("|");
    return new RegExp(e, D ? void 0 : "g");
  }(), "");
}

function j(D) {
  return D && D.__esModule && Object.prototype.hasOwnProperty.call(D, "default") ? D.default : D;
}

var J = {
  exports: {}
};

!function() {
  var D = {};
  J.exports = D, D.eastAsianWidth = function(D) {
    var e = D.charCodeAt(0), r = 2 == D.length ? D.charCodeAt(1) : 0, t = e;
    return 55296 <= e && e <= 56319 && 56320 <= r && r <= 57343 && (t = (e &= 1023) << 10 | (r &= 1023), 
    t += 65536), 12288 == t || 65281 <= t && t <= 65376 || 65504 <= t && t <= 65510 ? "F" : 8361 == t || 65377 <= t && t <= 65470 || 65474 <= t && t <= 65479 || 65482 <= t && t <= 65487 || 65490 <= t && t <= 65495 || 65498 <= t && t <= 65500 || 65512 <= t && t <= 65518 ? "H" : 4352 <= t && t <= 4447 || 4515 <= t && t <= 4519 || 4602 <= t && t <= 4607 || 9001 <= t && t <= 9002 || 11904 <= t && t <= 11929 || 11931 <= t && t <= 12019 || 12032 <= t && t <= 12245 || 12272 <= t && t <= 12283 || 12289 <= t && t <= 12350 || 12353 <= t && t <= 12438 || 12441 <= t && t <= 12543 || 12549 <= t && t <= 12589 || 12593 <= t && t <= 12686 || 12688 <= t && t <= 12730 || 12736 <= t && t <= 12771 || 12784 <= t && t <= 12830 || 12832 <= t && t <= 12871 || 12880 <= t && t <= 13054 || 13056 <= t && t <= 19903 || 19968 <= t && t <= 42124 || 42128 <= t && t <= 42182 || 43360 <= t && t <= 43388 || 44032 <= t && t <= 55203 || 55216 <= t && t <= 55238 || 55243 <= t && t <= 55291 || 63744 <= t && t <= 64255 || 65040 <= t && t <= 65049 || 65072 <= t && t <= 65106 || 65108 <= t && t <= 65126 || 65128 <= t && t <= 65131 || 110592 <= t && t <= 110593 || 127488 <= t && t <= 127490 || 127504 <= t && t <= 127546 || 127552 <= t && t <= 127560 || 127568 <= t && t <= 127569 || 131072 <= t && t <= 194367 || 177984 <= t && t <= 196605 || 196608 <= t && t <= 262141 ? "W" : 32 <= t && t <= 126 || 162 <= t && t <= 163 || 165 <= t && t <= 166 || 172 == t || 175 == t || 10214 <= t && t <= 10221 || 10629 <= t && t <= 10630 ? "Na" : 161 == t || 164 == t || 167 <= t && t <= 168 || 170 == t || 173 <= t && t <= 174 || 176 <= t && t <= 180 || 182 <= t && t <= 186 || 188 <= t && t <= 191 || 198 == t || 208 == t || 215 <= t && t <= 216 || 222 <= t && t <= 225 || 230 == t || 232 <= t && t <= 234 || 236 <= t && t <= 237 || 240 == t || 242 <= t && t <= 243 || 247 <= t && t <= 250 || 252 == t || 254 == t || 257 == t || 273 == t || 275 == t || 283 == t || 294 <= t && t <= 295 || 299 == t || 305 <= t && t <= 307 || 312 == t || 319 <= t && t <= 322 || 324 == t || 328 <= t && t <= 331 || 333 == t || 338 <= t && t <= 339 || 358 <= t && t <= 359 || 363 == t || 462 == t || 464 == t || 466 == t || 468 == t || 470 == t || 472 == t || 474 == t || 476 == t || 593 == t || 609 == t || 708 == t || 711 == t || 713 <= t && t <= 715 || 717 == t || 720 == t || 728 <= t && t <= 731 || 733 == t || 735 == t || 768 <= t && t <= 879 || 913 <= t && t <= 929 || 931 <= t && t <= 937 || 945 <= t && t <= 961 || 963 <= t && t <= 969 || 1025 == t || 1040 <= t && t <= 1103 || 1105 == t || 8208 == t || 8211 <= t && t <= 8214 || 8216 <= t && t <= 8217 || 8220 <= t && t <= 8221 || 8224 <= t && t <= 8226 || 8228 <= t && t <= 8231 || 8240 == t || 8242 <= t && t <= 8243 || 8245 == t || 8251 == t || 8254 == t || 8308 == t || 8319 == t || 8321 <= t && t <= 8324 || 8364 == t || 8451 == t || 8453 == t || 8457 == t || 8467 == t || 8470 == t || 8481 <= t && t <= 8482 || 8486 == t || 8491 == t || 8531 <= t && t <= 8532 || 8539 <= t && t <= 8542 || 8544 <= t && t <= 8555 || 8560 <= t && t <= 8569 || 8585 == t || 8592 <= t && t <= 8601 || 8632 <= t && t <= 8633 || 8658 == t || 8660 == t || 8679 == t || 8704 == t || 8706 <= t && t <= 8707 || 8711 <= t && t <= 8712 || 8715 == t || 8719 == t || 8721 == t || 8725 == t || 8730 == t || 8733 <= t && t <= 8736 || 8739 == t || 8741 == t || 8743 <= t && t <= 8748 || 8750 == t || 8756 <= t && t <= 8759 || 8764 <= t && t <= 8765 || 8776 == t || 8780 == t || 8786 == t || 8800 <= t && t <= 8801 || 8804 <= t && t <= 8807 || 8810 <= t && t <= 8811 || 8814 <= t && t <= 8815 || 8834 <= t && t <= 8835 || 8838 <= t && t <= 8839 || 8853 == t || 8857 == t || 8869 == t || 8895 == t || 8978 == t || 9312 <= t && t <= 9449 || 9451 <= t && t <= 9547 || 9552 <= t && t <= 9587 || 9600 <= t && t <= 9615 || 9618 <= t && t <= 9621 || 9632 <= t && t <= 9633 || 9635 <= t && t <= 9641 || 9650 <= t && t <= 9651 || 9654 <= t && t <= 9655 || 9660 <= t && t <= 9661 || 9664 <= t && t <= 9665 || 9670 <= t && t <= 9672 || 9675 == t || 9678 <= t && t <= 9681 || 9698 <= t && t <= 9701 || 9711 == t || 9733 <= t && t <= 9734 || 9737 == t || 9742 <= t && t <= 9743 || 9748 <= t && t <= 9749 || 9756 == t || 9758 == t || 9792 == t || 9794 == t || 9824 <= t && t <= 9825 || 9827 <= t && t <= 9829 || 9831 <= t && t <= 9834 || 9836 <= t && t <= 9837 || 9839 == t || 9886 <= t && t <= 9887 || 9918 <= t && t <= 9919 || 9924 <= t && t <= 9933 || 9935 <= t && t <= 9953 || 9955 == t || 9960 <= t && t <= 9983 || 10045 == t || 10071 == t || 10102 <= t && t <= 10111 || 11093 <= t && t <= 11097 || 12872 <= t && t <= 12879 || 57344 <= t && t <= 63743 || 65024 <= t && t <= 65039 || 65533 == t || 127232 <= t && t <= 127242 || 127248 <= t && t <= 127277 || 127280 <= t && t <= 127337 || 127344 <= t && t <= 127386 || 917760 <= t && t <= 917999 || 983040 <= t && t <= 1048573 || 1048576 <= t && t <= 1114109 ? "A" : "N";
  }, D.characterLength = function(D) {
    var e = this.eastAsianWidth(D);
    return "F" == e || "W" == e || "A" == e ? 2 : 1;
  };
  function F(D) {
    return D.match(/[\uD800-\uDBFF][\uDC00-\uDFFF]|[^\uD800-\uDFFF]/g) || [];
  }
  D.length = function(D) {
    for (var e = F(D), r = 0, t = 0; t < e.length; t++) {
      r += this.characterLength(e[t]);
    }
    return r;
  }, D.slice = function(e, r, t) {
    textLen = D.length(e), t = t || 1, (r = r || 0) < 0 && (r = textLen + r), t < 0 && (t = textLen + t);
    for (var n = "", i = 0, a = F(e), s = 0; s < a.length; s++) {
      var c = a[s], l = D.length(c);
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

var X = j(J.exports);

var Z = j((function() {
  return /\uD83C\uDFF4\uDB40\uDC67\uDB40\uDC62(?:\uDB40\uDC77\uDB40\uDC6C\uDB40\uDC73|\uDB40\uDC73\uDB40\uDC63\uDB40\uDC74|\uDB40\uDC65\uDB40\uDC6E\uDB40\uDC67)\uDB40\uDC7F|(?:\uD83E\uDDD1\uD83C\uDFFF\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFF\u200D\uD83E\uDD1D\u200D(?:\uD83D[\uDC68\uDC69]))(?:\uD83C[\uDFFB-\uDFFE])|(?:\uD83E\uDDD1\uD83C\uDFFE\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFE\u200D\uD83E\uDD1D\u200D(?:\uD83D[\uDC68\uDC69]))(?:\uD83C[\uDFFB-\uDFFD\uDFFF])|(?:\uD83E\uDDD1\uD83C\uDFFD\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFD\u200D\uD83E\uDD1D\u200D(?:\uD83D[\uDC68\uDC69]))(?:\uD83C[\uDFFB\uDFFC\uDFFE\uDFFF])|(?:\uD83E\uDDD1\uD83C\uDFFC\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFC\u200D\uD83E\uDD1D\u200D(?:\uD83D[\uDC68\uDC69]))(?:\uD83C[\uDFFB\uDFFD-\uDFFF])|(?:\uD83E\uDDD1\uD83C\uDFFB\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D)?\uD83E\uDDD1|\uD83D\uDC69\uD83C\uDFFB\u200D\uD83E\uDD1D\u200D(?:\uD83D[\uDC68\uDC69]))(?:\uD83C[\uDFFC-\uDFFF])|\uD83D\uDC68(?:\uD83C\uDFFB(?:\u200D(?:\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFF])|\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFF]))|\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFC-\uDFFF])|[\u2695\u2696\u2708]\uFE0F|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD]))?|(?:\uD83C[\uDFFC-\uDFFF])\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFF])|\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFF]))|\u200D(?:\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D)?\uD83D\uDC68|(?:\uD83D[\uDC68\uDC69])\u200D(?:\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67]))|\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67])|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFF\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFE])|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFE\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB-\uDFFD\uDFFF])|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFD\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB\uDFFC\uDFFE\uDFFF])|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFC\u200D(?:\uD83E\uDD1D\u200D\uD83D\uDC68(?:\uD83C[\uDFFB\uDFFD-\uDFFF])|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|(?:\uD83C\uDFFF\u200D[\u2695\u2696\u2708]|\uD83C\uDFFE\u200D[\u2695\u2696\u2708]|\uD83C\uDFFD\u200D[\u2695\u2696\u2708]|\uD83C\uDFFC\u200D[\u2695\u2696\u2708]|\u200D[\u2695\u2696\u2708])\uFE0F|\u200D(?:(?:\uD83D[\uDC68\uDC69])\u200D(?:\uD83D[\uDC66\uDC67])|\uD83D[\uDC66\uDC67])|\uD83C\uDFFF|\uD83C\uDFFE|\uD83C\uDFFD|\uD83C\uDFFC)?|(?:\uD83D\uDC69(?:\uD83C\uDFFB\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D(?:\uD83D[\uDC68\uDC69])|\uD83D[\uDC68\uDC69])|(?:\uD83C[\uDFFC-\uDFFF])\u200D\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D(?:\uD83D[\uDC68\uDC69])|\uD83D[\uDC68\uDC69]))|\uD83E\uDDD1(?:\uD83C[\uDFFB-\uDFFF])\u200D\uD83E\uDD1D\u200D\uD83E\uDDD1)(?:\uD83C[\uDFFB-\uDFFF])|\uD83D\uDC69\u200D\uD83D\uDC69\u200D(?:\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67]))|\uD83D\uDC69(?:\u200D(?:\u2764\uFE0F\u200D(?:\uD83D\uDC8B\u200D(?:\uD83D[\uDC68\uDC69])|\uD83D[\uDC68\uDC69])|\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFF\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFE\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFD\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFC\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFB\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD]))|\uD83E\uDDD1(?:\u200D(?:\uD83E\uDD1D\u200D\uD83E\uDDD1|\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFF\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFE\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFD\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFC\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD])|\uD83C\uDFFB\u200D(?:\uD83C[\uDF3E\uDF73\uDF7C\uDF84\uDF93\uDFA4\uDFA8\uDFEB\uDFED]|\uD83D[\uDCBB\uDCBC\uDD27\uDD2C\uDE80\uDE92]|\uD83E[\uDDAF-\uDDB3\uDDBC\uDDBD]))|\uD83D\uDC69\u200D\uD83D\uDC66\u200D\uD83D\uDC66|\uD83D\uDC69\u200D\uD83D\uDC69\u200D(?:\uD83D[\uDC66\uDC67])|\uD83D\uDC69\u200D\uD83D\uDC67\u200D(?:\uD83D[\uDC66\uDC67])|(?:\uD83D\uDC41\uFE0F\u200D\uD83D\uDDE8|\uD83E\uDDD1(?:\uD83C\uDFFF\u200D[\u2695\u2696\u2708]|\uD83C\uDFFE\u200D[\u2695\u2696\u2708]|\uD83C\uDFFD\u200D[\u2695\u2696\u2708]|\uD83C\uDFFC\u200D[\u2695\u2696\u2708]|\uD83C\uDFFB\u200D[\u2695\u2696\u2708]|\u200D[\u2695\u2696\u2708])|\uD83D\uDC69(?:\uD83C\uDFFF\u200D[\u2695\u2696\u2708]|\uD83C\uDFFE\u200D[\u2695\u2696\u2708]|\uD83C\uDFFD\u200D[\u2695\u2696\u2708]|\uD83C\uDFFC\u200D[\u2695\u2696\u2708]|\uD83C\uDFFB\u200D[\u2695\u2696\u2708]|\u200D[\u2695\u2696\u2708])|\uD83D\uDE36\u200D\uD83C\uDF2B|\uD83C\uDFF3\uFE0F\u200D\u26A7|\uD83D\uDC3B\u200D\u2744|(?:(?:\uD83C[\uDFC3\uDFC4\uDFCA]|\uD83D[\uDC6E\uDC70\uDC71\uDC73\uDC77\uDC81\uDC82\uDC86\uDC87\uDE45-\uDE47\uDE4B\uDE4D\uDE4E\uDEA3\uDEB4-\uDEB6]|\uD83E[\uDD26\uDD35\uDD37-\uDD39\uDD3D\uDD3E\uDDB8\uDDB9\uDDCD-\uDDCF\uDDD4\uDDD6-\uDDDD])(?:\uD83C[\uDFFB-\uDFFF])|\uD83D\uDC6F|\uD83E[\uDD3C\uDDDE\uDDDF])\u200D[\u2640\u2642]|(?:\u26F9|\uD83C[\uDFCB\uDFCC]|\uD83D\uDD75)(?:\uFE0F|\uD83C[\uDFFB-\uDFFF])\u200D[\u2640\u2642]|\uD83C\uDFF4\u200D\u2620|(?:\uD83C[\uDFC3\uDFC4\uDFCA]|\uD83D[\uDC6E\uDC70\uDC71\uDC73\uDC77\uDC81\uDC82\uDC86\uDC87\uDE45-\uDE47\uDE4B\uDE4D\uDE4E\uDEA3\uDEB4-\uDEB6]|\uD83E[\uDD26\uDD35\uDD37-\uDD39\uDD3D\uDD3E\uDDB8\uDDB9\uDDCD-\uDDCF\uDDD4\uDDD6-\uDDDD])\u200D[\u2640\u2642]|[\xA9\xAE\u203C\u2049\u2122\u2139\u2194-\u2199\u21A9\u21AA\u2328\u23CF\u23ED-\u23EF\u23F1\u23F2\u23F8-\u23FA\u24C2\u25AA\u25AB\u25B6\u25C0\u25FB\u25FC\u2600-\u2604\u260E\u2611\u2618\u2620\u2622\u2623\u2626\u262A\u262E\u262F\u2638-\u263A\u2640\u2642\u265F\u2660\u2663\u2665\u2666\u2668\u267B\u267E\u2692\u2694-\u2697\u2699\u269B\u269C\u26A0\u26A7\u26B0\u26B1\u26C8\u26CF\u26D1\u26D3\u26E9\u26F0\u26F1\u26F4\u26F7\u26F8\u2702\u2708\u2709\u270F\u2712\u2714\u2716\u271D\u2721\u2733\u2734\u2744\u2747\u2763\u27A1\u2934\u2935\u2B05-\u2B07\u3030\u303D\u3297\u3299]|\uD83C[\uDD70\uDD71\uDD7E\uDD7F\uDE02\uDE37\uDF21\uDF24-\uDF2C\uDF36\uDF7D\uDF96\uDF97\uDF99-\uDF9B\uDF9E\uDF9F\uDFCD\uDFCE\uDFD4-\uDFDF\uDFF5\uDFF7]|\uD83D[\uDC3F\uDCFD\uDD49\uDD4A\uDD6F\uDD70\uDD73\uDD76-\uDD79\uDD87\uDD8A-\uDD8D\uDDA5\uDDA8\uDDB1\uDDB2\uDDBC\uDDC2-\uDDC4\uDDD1-\uDDD3\uDDDC-\uDDDE\uDDE1\uDDE3\uDDE8\uDDEF\uDDF3\uDDFA\uDECB\uDECD-\uDECF\uDEE0-\uDEE5\uDEE9\uDEF0\uDEF3])\uFE0F|\uD83C\uDFF3\uFE0F\u200D\uD83C\uDF08|\uD83D\uDC69\u200D\uD83D\uDC67|\uD83D\uDC69\u200D\uD83D\uDC66|\uD83D\uDE35\u200D\uD83D\uDCAB|\uD83D\uDE2E\u200D\uD83D\uDCA8|\uD83D\uDC15\u200D\uD83E\uDDBA|\uD83E\uDDD1(?:\uD83C\uDFFF|\uD83C\uDFFE|\uD83C\uDFFD|\uD83C\uDFFC|\uD83C\uDFFB)?|\uD83D\uDC69(?:\uD83C\uDFFF|\uD83C\uDFFE|\uD83C\uDFFD|\uD83C\uDFFC|\uD83C\uDFFB)?|\uD83C\uDDFD\uD83C\uDDF0|\uD83C\uDDF6\uD83C\uDDE6|\uD83C\uDDF4\uD83C\uDDF2|\uD83D\uDC08\u200D\u2B1B|\u2764\uFE0F\u200D(?:\uD83D\uDD25|\uD83E\uDE79)|\uD83D\uDC41\uFE0F|\uD83C\uDFF3\uFE0F|\uD83C\uDDFF(?:\uD83C[\uDDE6\uDDF2\uDDFC])|\uD83C\uDDFE(?:\uD83C[\uDDEA\uDDF9])|\uD83C\uDDFC(?:\uD83C[\uDDEB\uDDF8])|\uD83C\uDDFB(?:\uD83C[\uDDE6\uDDE8\uDDEA\uDDEC\uDDEE\uDDF3\uDDFA])|\uD83C\uDDFA(?:\uD83C[\uDDE6\uDDEC\uDDF2\uDDF3\uDDF8\uDDFE\uDDFF])|\uD83C\uDDF9(?:\uD83C[\uDDE6\uDDE8\uDDE9\uDDEB-\uDDED\uDDEF-\uDDF4\uDDF7\uDDF9\uDDFB\uDDFC\uDDFF])|\uD83C\uDDF8(?:\uD83C[\uDDE6-\uDDEA\uDDEC-\uDDF4\uDDF7-\uDDF9\uDDFB\uDDFD-\uDDFF])|\uD83C\uDDF7(?:\uD83C[\uDDEA\uDDF4\uDDF8\uDDFA\uDDFC])|\uD83C\uDDF5(?:\uD83C[\uDDE6\uDDEA-\uDDED\uDDF0-\uDDF3\uDDF7-\uDDF9\uDDFC\uDDFE])|\uD83C\uDDF3(?:\uD83C[\uDDE6\uDDE8\uDDEA-\uDDEC\uDDEE\uDDF1\uDDF4\uDDF5\uDDF7\uDDFA\uDDFF])|\uD83C\uDDF2(?:\uD83C[\uDDE6\uDDE8-\uDDED\uDDF0-\uDDFF])|\uD83C\uDDF1(?:\uD83C[\uDDE6-\uDDE8\uDDEE\uDDF0\uDDF7-\uDDFB\uDDFE])|\uD83C\uDDF0(?:\uD83C[\uDDEA\uDDEC-\uDDEE\uDDF2\uDDF3\uDDF5\uDDF7\uDDFC\uDDFE\uDDFF])|\uD83C\uDDEF(?:\uD83C[\uDDEA\uDDF2\uDDF4\uDDF5])|\uD83C\uDDEE(?:\uD83C[\uDDE8-\uDDEA\uDDF1-\uDDF4\uDDF6-\uDDF9])|\uD83C\uDDED(?:\uD83C[\uDDF0\uDDF2\uDDF3\uDDF7\uDDF9\uDDFA])|\uD83C\uDDEC(?:\uD83C[\uDDE6\uDDE7\uDDE9-\uDDEE\uDDF1-\uDDF3\uDDF5-\uDDFA\uDDFC\uDDFE])|\uD83C\uDDEB(?:\uD83C[\uDDEE-\uDDF0\uDDF2\uDDF4\uDDF7])|\uD83C\uDDEA(?:\uD83C[\uDDE6\uDDE8\uDDEA\uDDEC\uDDED\uDDF7-\uDDFA])|\uD83C\uDDE9(?:\uD83C[\uDDEA\uDDEC\uDDEF\uDDF0\uDDF2\uDDF4\uDDFF])|\uD83C\uDDE8(?:\uD83C[\uDDE6\uDDE8\uDDE9\uDDEB-\uDDEE\uDDF0-\uDDF5\uDDF7\uDDFA-\uDDFF])|\uD83C\uDDE7(?:\uD83C[\uDDE6\uDDE7\uDDE9-\uDDEF\uDDF1-\uDDF4\uDDF6-\uDDF9\uDDFB\uDDFC\uDDFE\uDDFF])|\uD83C\uDDE6(?:\uD83C[\uDDE8-\uDDEC\uDDEE\uDDF1\uDDF2\uDDF4\uDDF6-\uDDFA\uDDFC\uDDFD\uDDFF])|[#\*0-9]\uFE0F\u20E3|\u2764\uFE0F|(?:\uD83C[\uDFC3\uDFC4\uDFCA]|\uD83D[\uDC6E\uDC70\uDC71\uDC73\uDC77\uDC81\uDC82\uDC86\uDC87\uDE45-\uDE47\uDE4B\uDE4D\uDE4E\uDEA3\uDEB4-\uDEB6]|\uD83E[\uDD26\uDD35\uDD37-\uDD39\uDD3D\uDD3E\uDDB8\uDDB9\uDDCD-\uDDCF\uDDD4\uDDD6-\uDDDD])(?:\uD83C[\uDFFB-\uDFFF])|(?:\u26F9|\uD83C[\uDFCB\uDFCC]|\uD83D\uDD75)(?:\uFE0F|\uD83C[\uDFFB-\uDFFF])|\uD83C\uDFF4|(?:[\u270A\u270B]|\uD83C[\uDF85\uDFC2\uDFC7]|\uD83D[\uDC42\uDC43\uDC46-\uDC50\uDC66\uDC67\uDC6B-\uDC6D\uDC72\uDC74-\uDC76\uDC78\uDC7C\uDC83\uDC85\uDC8F\uDC91\uDCAA\uDD7A\uDD95\uDD96\uDE4C\uDE4F\uDEC0\uDECC]|\uD83E[\uDD0C\uDD0F\uDD18-\uDD1C\uDD1E\uDD1F\uDD30-\uDD34\uDD36\uDD77\uDDB5\uDDB6\uDDBB\uDDD2\uDDD3\uDDD5])(?:\uD83C[\uDFFB-\uDFFF])|(?:[\u261D\u270C\u270D]|\uD83D[\uDD74\uDD90])(?:\uFE0F|\uD83C[\uDFFB-\uDFFF])|[\u270A\u270B]|\uD83C[\uDF85\uDFC2\uDFC7]|\uD83D[\uDC08\uDC15\uDC3B\uDC42\uDC43\uDC46-\uDC50\uDC66\uDC67\uDC6B-\uDC6D\uDC72\uDC74-\uDC76\uDC78\uDC7C\uDC83\uDC85\uDC8F\uDC91\uDCAA\uDD7A\uDD95\uDD96\uDE2E\uDE35\uDE36\uDE4C\uDE4F\uDEC0\uDECC]|\uD83E[\uDD0C\uDD0F\uDD18-\uDD1C\uDD1E\uDD1F\uDD30-\uDD34\uDD36\uDD77\uDDB5\uDDB6\uDDBB\uDDD2\uDDD3\uDDD5]|\uD83C[\uDFC3\uDFC4\uDFCA]|\uD83D[\uDC6E\uDC70\uDC71\uDC73\uDC77\uDC81\uDC82\uDC86\uDC87\uDE45-\uDE47\uDE4B\uDE4D\uDE4E\uDEA3\uDEB4-\uDEB6]|\uD83E[\uDD26\uDD35\uDD37-\uDD39\uDD3D\uDD3E\uDDB8\uDDB9\uDDCD-\uDDCF\uDDD4\uDDD6-\uDDDD]|\uD83D\uDC6F|\uD83E[\uDD3C\uDDDE\uDDDF]|[\u231A\u231B\u23E9-\u23EC\u23F0\u23F3\u25FD\u25FE\u2614\u2615\u2648-\u2653\u267F\u2693\u26A1\u26AA\u26AB\u26BD\u26BE\u26C4\u26C5\u26CE\u26D4\u26EA\u26F2\u26F3\u26F5\u26FA\u26FD\u2705\u2728\u274C\u274E\u2753-\u2755\u2757\u2795-\u2797\u27B0\u27BF\u2B1B\u2B1C\u2B50\u2B55]|\uD83C[\uDC04\uDCCF\uDD8E\uDD91-\uDD9A\uDE01\uDE1A\uDE2F\uDE32-\uDE36\uDE38-\uDE3A\uDE50\uDE51\uDF00-\uDF20\uDF2D-\uDF35\uDF37-\uDF7C\uDF7E-\uDF84\uDF86-\uDF93\uDFA0-\uDFC1\uDFC5\uDFC6\uDFC8\uDFC9\uDFCF-\uDFD3\uDFE0-\uDFF0\uDFF8-\uDFFF]|\uD83D[\uDC00-\uDC07\uDC09-\uDC14\uDC16-\uDC3A\uDC3C-\uDC3E\uDC40\uDC44\uDC45\uDC51-\uDC65\uDC6A\uDC79-\uDC7B\uDC7D-\uDC80\uDC84\uDC88-\uDC8E\uDC90\uDC92-\uDCA9\uDCAB-\uDCFC\uDCFF-\uDD3D\uDD4B-\uDD4E\uDD50-\uDD67\uDDA4\uDDFB-\uDE2D\uDE2F-\uDE34\uDE37-\uDE44\uDE48-\uDE4A\uDE80-\uDEA2\uDEA4-\uDEB3\uDEB7-\uDEBF\uDEC1-\uDEC5\uDED0-\uDED2\uDED5-\uDED7\uDEEB\uDEEC\uDEF4-\uDEFC\uDFE0-\uDFEB]|\uD83E[\uDD0D\uDD0E\uDD10-\uDD17\uDD1D\uDD20-\uDD25\uDD27-\uDD2F\uDD3A\uDD3F-\uDD45\uDD47-\uDD76\uDD78\uDD7A-\uDDB4\uDDB7\uDDBA\uDDBC-\uDDCB\uDDD0\uDDE0-\uDDFF\uDE70-\uDE74\uDE78-\uDE7A\uDE80-\uDE86\uDE90-\uDEA8\uDEB0-\uDEB6\uDEC0-\uDEC2\uDED0-\uDED6]|(?:[\u231A\u231B\u23E9-\u23EC\u23F0\u23F3\u25FD\u25FE\u2614\u2615\u2648-\u2653\u267F\u2693\u26A1\u26AA\u26AB\u26BD\u26BE\u26C4\u26C5\u26CE\u26D4\u26EA\u26F2\u26F3\u26F5\u26FA\u26FD\u2705\u270A\u270B\u2728\u274C\u274E\u2753-\u2755\u2757\u2795-\u2797\u27B0\u27BF\u2B1B\u2B1C\u2B50\u2B55]|\uD83C[\uDC04\uDCCF\uDD8E\uDD91-\uDD9A\uDDE6-\uDDFF\uDE01\uDE1A\uDE2F\uDE32-\uDE36\uDE38-\uDE3A\uDE50\uDE51\uDF00-\uDF20\uDF2D-\uDF35\uDF37-\uDF7C\uDF7E-\uDF93\uDFA0-\uDFCA\uDFCF-\uDFD3\uDFE0-\uDFF0\uDFF4\uDFF8-\uDFFF]|\uD83D[\uDC00-\uDC3E\uDC40\uDC42-\uDCFC\uDCFF-\uDD3D\uDD4B-\uDD4E\uDD50-\uDD67\uDD7A\uDD95\uDD96\uDDA4\uDDFB-\uDE4F\uDE80-\uDEC5\uDECC\uDED0-\uDED2\uDED5-\uDED7\uDEEB\uDEEC\uDEF4-\uDEFC\uDFE0-\uDFEB]|\uD83E[\uDD0C-\uDD3A\uDD3C-\uDD45\uDD47-\uDD78\uDD7A-\uDDCB\uDDCD-\uDDFF\uDE70-\uDE74\uDE78-\uDE7A\uDE80-\uDE86\uDE90-\uDEA8\uDEB0-\uDEB6\uDEC0-\uDEC2\uDED0-\uDED6])|(?:[#\*0-9\xA9\xAE\u203C\u2049\u2122\u2139\u2194-\u2199\u21A9\u21AA\u231A\u231B\u2328\u23CF\u23E9-\u23F3\u23F8-\u23FA\u24C2\u25AA\u25AB\u25B6\u25C0\u25FB-\u25FE\u2600-\u2604\u260E\u2611\u2614\u2615\u2618\u261D\u2620\u2622\u2623\u2626\u262A\u262E\u262F\u2638-\u263A\u2640\u2642\u2648-\u2653\u265F\u2660\u2663\u2665\u2666\u2668\u267B\u267E\u267F\u2692-\u2697\u2699\u269B\u269C\u26A0\u26A1\u26A7\u26AA\u26AB\u26B0\u26B1\u26BD\u26BE\u26C4\u26C5\u26C8\u26CE\u26CF\u26D1\u26D3\u26D4\u26E9\u26EA\u26F0-\u26F5\u26F7-\u26FA\u26FD\u2702\u2705\u2708-\u270D\u270F\u2712\u2714\u2716\u271D\u2721\u2728\u2733\u2734\u2744\u2747\u274C\u274E\u2753-\u2755\u2757\u2763\u2764\u2795-\u2797\u27A1\u27B0\u27BF\u2934\u2935\u2B05-\u2B07\u2B1B\u2B1C\u2B50\u2B55\u3030\u303D\u3297\u3299]|\uD83C[\uDC04\uDCCF\uDD70\uDD71\uDD7E\uDD7F\uDD8E\uDD91-\uDD9A\uDDE6-\uDDFF\uDE01\uDE02\uDE1A\uDE2F\uDE32-\uDE3A\uDE50\uDE51\uDF00-\uDF21\uDF24-\uDF93\uDF96\uDF97\uDF99-\uDF9B\uDF9E-\uDFF0\uDFF3-\uDFF5\uDFF7-\uDFFF]|\uD83D[\uDC00-\uDCFD\uDCFF-\uDD3D\uDD49-\uDD4E\uDD50-\uDD67\uDD6F\uDD70\uDD73-\uDD7A\uDD87\uDD8A-\uDD8D\uDD90\uDD95\uDD96\uDDA4\uDDA5\uDDA8\uDDB1\uDDB2\uDDBC\uDDC2-\uDDC4\uDDD1-\uDDD3\uDDDC-\uDDDE\uDDE1\uDDE3\uDDE8\uDDEF\uDDF3\uDDFA-\uDE4F\uDE80-\uDEC5\uDECB-\uDED2\uDED5-\uDED7\uDEE0-\uDEE5\uDEE9\uDEEB\uDEEC\uDEF0\uDEF3-\uDEFC\uDFE0-\uDFEB]|\uD83E[\uDD0C-\uDD3A\uDD3C-\uDD45\uDD47-\uDD78\uDD7A-\uDDCB\uDDCD-\uDDFF\uDE70-\uDE74\uDE78-\uDE7A\uDE80-\uDE86\uDE90-\uDEA8\uDEB0-\uDEB6\uDEC0-\uDEC2\uDED0-\uDED6])\uFE0F|(?:[\u261D\u26F9\u270A-\u270D]|\uD83C[\uDF85\uDFC2-\uDFC4\uDFC7\uDFCA-\uDFCC]|\uD83D[\uDC42\uDC43\uDC46-\uDC50\uDC66-\uDC78\uDC7C\uDC81-\uDC83\uDC85-\uDC87\uDC8F\uDC91\uDCAA\uDD74\uDD75\uDD7A\uDD90\uDD95\uDD96\uDE45-\uDE47\uDE4B-\uDE4F\uDEA3\uDEB4-\uDEB6\uDEC0\uDECC]|\uD83E[\uDD0C\uDD0F\uDD18-\uDD1F\uDD26\uDD30-\uDD39\uDD3C-\uDD3E\uDD77\uDDB5\uDDB6\uDDB8\uDDB9\uDDBB\uDDCD-\uDDCF\uDDD1-\uDDDD])/g;
}));

function A(D, e = {}) {
  if ("string" != typeof D || 0 === D.length || (e = {
    ambiguousIsNarrow: !0,
    ...e
  }, 0 === (D = S$1(D)).length)) {
    return 0;
  }
  D = D.replace(Z(), "  ");
  var r = e.ambiguousIsNarrow ? 1 : 2;
  var t = 0;
  for (var n of D) {
    var i = n.codePointAt(0);
    if (i <= 31 || i >= 127 && i <= 159 || i >= 768 && i <= 879) {
      continue;
    }
    switch (X.eastAsianWidth(n)) {
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

var T = (D = 0) => e => `[${e + D}m`, P = (D = 0) => e => `[${38 + D};5;${e}m`, W = (D = 0) => (e, r, t) => `[${38 + D};2;${e};${r};${t}m`, Q = {
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

Object.keys(Q.modifier);

Object.keys(Q.color), Object.keys(Q.bgColor);

var uu = function tD() {
  var D = new Map;
  for (var [e, r] of Object.entries(Q)) {
    for (var [t, n] of Object.entries(r)) {
      Q[t] = {
        open: `[${n[0]}m`,
        close: `[${n[1]}m`
      }, r[t] = Q[t], D.set(n[0], n[1]);
    }
    Object.defineProperty(Q, e, {
      value: r,
      enumerable: !1
    });
  }
  return Object.defineProperty(Q, "codes", {
    value: D,
    enumerable: !1
  }), Q.color.close = "[39m", Q.bgColor.close = "[49m", Q.color.ansi = T(), Q.color.ansi256 = P(), 
  Q.color.ansi16m = W(), Q.bgColor.ansi = T(10), Q.bgColor.ansi256 = P(10), Q.bgColor.ansi16m = W(10), 
  Object.defineProperties(Q, {
    rgbToAnsi256: {
      value: (D, e, r) => D === e && e === r ? D < 8 ? 16 : D > 248 ? 231 : Math.round((D - 8) / 247 * 24) + 232 : 16 + 36 * Math.round(D / 255 * 5) + 6 * Math.round(e / 255 * 5) + Math.round(r / 255 * 5),
      enumerable: !1
    },
    hexToRgb: {
      value: D => {
        var e = /[a-f\d]{6}|[a-f\d]{3}/i.exec(D.toString(16));
        if (!e) {
          return [ 0, 0, 0 ];
        }
        var [r] = e;
        3 === r.length && (r = [ ...r ].map((D => D + D)).join(""));
        var t = Number.parseInt(r, 16);
        return [ t >> 16 & 255, t >> 8 & 255, 255 & t ];
      },
      enumerable: !1
    },
    hexToAnsi256: {
      value: D => Q.rgbToAnsi256(...Q.hexToRgb(D)),
      enumerable: !1
    },
    ansi256ToAnsi: {
      value: D => {
        if (D < 8) {
          return 30 + D;
        }
        if (D < 16) {
          return D - 8 + 90;
        }
        var e, r, t;
        if (D >= 232) {
          r = e = (10 * (D - 232) + 8) / 255, t = e;
        } else {
          var n = (D -= 16) % 36;
          e = Math.floor(D / 36) / 5, r = Math.floor(n / 6) / 5, t = n % 6 / 5;
        }
        var i = 2 * Math.max(e, r, t);
        if (0 === i) {
          return 30;
        }
        var a = 30 + (Math.round(t) << 2 | Math.round(r) << 1 | Math.round(e));
        return 2 === i && (a += 60), a;
      },
      enumerable: !1
    },
    rgbToAnsi: {
      value: (D, e, r) => Q.ansi256ToAnsi(Q.rgbToAnsi256(D, e, r)),
      enumerable: !1
    },
    hexToAnsi: {
      value: D => Q.ansi256ToAnsi(Q.hexToAnsi256(D)),
      enumerable: !1
    }
  }), Q;
}(), Du = new Set([ "", "" ]), eu = "]8;;", N = D => `${Du.values().next().value}[${D}m`, L = D => `${Du.values().next().value}${eu}${D}`, y$1 = (D, e, r) => {
  var t = [ ...e ];
  var n = !1, i = !1, a = A(S$1(D[D.length - 1]));
  for (var [s, c] of t.entries()) {
    var l = A(c);
    if (a + l <= r ? D[D.length - 1] += c : (D.push(c), a = 0), Du.has(c) && (n = !0, 
    i = t.slice(s + 1).join("").startsWith(eu)), n) {
      i ? "" === c && (n = !1, i = !1) : "m" === c && (n = !1);
      continue;
    }
    (a += l) === r && s < t.length - 1 && (D.push(""), a = 0);
  }
  !a && D[D.length - 1].length > 0 && D.length > 1 && (D[D.length - 2] += D.pop());
}, ED = (D, e, r = {}) => {
  if (!1 !== r.trim && "" === D.trim()) {
    return "";
  }
  var t, n, i = "";
  var a = (D => D.split(" ").map((D => A(D))))(D);
  var s = [ "" ];
  for (var [c, l] of D.split(" ").entries()) {
    !1 !== r.trim && (s[s.length - 1] = s[s.length - 1].trimStart());
    var d = A(s[s.length - 1]);
    if (0 !== c && (d >= e && (!1 === r.wordWrap || !1 === r.trim) && (s.push(""), d = 0), 
    (d > 0 || !1 === r.trim) && (s[s.length - 1] += " ", d++)), r.hard && a[c] > e) {
      var p = 1 + Math.floor((a[c] - (e - d) - 1) / e);
      Math.floor((a[c] - 1) / e) < p && s.push(""), y$1(s, l, e);
      continue;
    }
    if (d + a[c] > e && d > 0 && a[c] > 0) {
      if (!1 === r.wordWrap && d < e) {
        y$1(s, l, e);
        continue;
      }
      s.push("");
    }
    if (d + a[c] > e && !1 === r.wordWrap) {
      y$1(s, l, e);
      continue;
    }
    s[s.length - 1] += l;
  }
  !1 !== r.trim && (s = s.map((D => (D => {
    var e = D.split(" ");
    var r = e.length;
    for (;r > 0 && !(A(e[r - 1]) > 0); ) {
      r--;
    }
    return r === e.length ? D : e.slice(0, r).join(" ") + e.slice(r).join("");
  })(D))));
  var E = [ ...s.join("\n") ];
  for (var [f, h] of E.entries()) {
    if (i += h, Du.has(h)) {
      var {groups: m} = new RegExp(`(?:\\[(?<code>\\d+)m|\\${eu}(?<uri>.*))`).exec(E.slice(f).join("")) || {
        groups: {}
      };
      if (void 0 !== m.code) {
        var g = Number.parseFloat(m.code);
        t = 39 === g ? void 0 : g;
      } else {
        void 0 !== m.uri && (n = 0 === m.uri.length ? void 0 : m.uri);
      }
    }
    var B = uu.codes.get(Number(t));
    "\n" === E[f + 1] ? (n && (i += L("")), t && B && (i += N(B))) : "\n" === h && (t && B && (i += N(t)), 
    n && (i += L(n)));
  }
  return i;
};

function R(D, e, r) {
  return String(D).normalize().replace(/\r\n/g, "\n").split("\n").map((D => ED(D, e, r))).join("\n");
}

var ru = Object.defineProperty, a$1 = (D, e, r) => (((D, e, r) => {
  e in D ? ru(D, e, {
    enumerable: !0,
    configurable: !0,
    writable: !0,
    value: r
  }) : D[e] = r;
})(D, "symbol" != typeof e ? e + "" : e, r), r);

var tu = Symbol("clack:cancel");

function hD(D) {
  return D === tu;
}

function v(D, e) {
  D.isTTY && D.setRawMode(e);
}

var nu = new Map([ [ "k", "up" ], [ "j", "down" ], [ "h", "left" ], [ "l", "right" ] ]), iu = new Set([ "up", "down", "left", "right", "space", "enter" ]);

let au = class x {
  constructor({render: D, input: t = e, output: n = r, ...i}, a = !0) {
    a$1(this, "input"), a$1(this, "output"), a$1(this, "rl"), a$1(this, "opts"), a$1(this, "_track", !1), 
    a$1(this, "_render"), a$1(this, "_cursor", 0), a$1(this, "state", "initial"), a$1(this, "value"), 
    a$1(this, "error", ""), a$1(this, "subscribers", new Map), a$1(this, "_prevFrame", ""), 
    this.opts = i, this.onKeypress = this.onKeypress.bind(this), this.close = this.close.bind(this), 
    this.render = this.render.bind(this), this._render = D.bind(this), this._track = a, 
    this.input = t, this.output = n;
  }
  prompt() {
    var D = new i(0);
    return D._write = (D, e, r) => {
      this._track && (this.value = this.rl.line.replace(/\t/g, ""), this._cursor = this.rl.cursor, 
      this.emit("value", this.value)), r();
    }, this.input.pipe(D), this.rl = n.createInterface({
      input: this.input,
      output: D,
      tabSize: 2,
      prompt: "",
      escapeCodeTimeout: 50
    }), n.emitKeypressEvents(this.input, this.rl), this.rl.prompt(), void 0 !== this.opts.initialValue && this._track && this.rl.write(this.opts.initialValue), 
    this.input.on("keypress", this.onKeypress), v(this.input, !0), this.output.on("resize", this.render), 
    this.render(), new Promise(((D, e) => {
      this.once("submit", (() => {
        this.output.write(K.cursor.show), this.output.off("resize", this.render), v(this.input, !1), 
        D(this.value);
      })), this.once("cancel", (() => {
        this.output.write(K.cursor.show), this.output.off("resize", this.render), v(this.input, !1), 
        D(tu);
      }));
    }));
  }
  on(D, e) {
    var r = this.subscribers.get(D) ?? [];
    r.push({
      cb: e
    }), this.subscribers.set(D, r);
  }
  once(D, e) {
    var r = this.subscribers.get(D) ?? [];
    r.push({
      cb: e,
      once: !0
    }), this.subscribers.set(D, r);
  }
  emit(D, ...e) {
    var r = this.subscribers.get(D) ?? [], t = [];
    var _loop = function(D) {
      D.cb(...e), D.once && t.push((() => r.splice(r.indexOf(D), 1)));
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
  onKeypress(D, e) {
    if ("error" === this.state && (this.state = "active"), e?.name && !this._track && nu.has(e.name) && this.emit("cursor", nu.get(e.name)), 
    e?.name && iu.has(e.name) && this.emit("cursor", e.name), D && ("y" === D.toLowerCase() || "n" === D.toLowerCase()) && this.emit("confirm", "y" === D.toLowerCase()), 
    "\t" === D && this.opts.placeholder && (this.value || (this.rl.write(this.opts.placeholder), 
    this.emit("value", this.opts.placeholder))), D && this.emit("key", D.toLowerCase()), 
    "return" === e?.name) {
      if (this.opts.validate) {
        var r = this.opts.validate(this.value);
        r && (this.error = r, this.state = "error", this.rl.write(this.value));
      }
      "error" !== this.state && (this.state = "submit");
    }
    "" === D && (this.state = "cancel"), ("submit" === this.state || "cancel" === this.state) && this.emit("finalize"), 
    this.render(), ("submit" === this.state || "cancel" === this.state) && this.close();
  }
  close() {
    this.input.unpipe(), this.input.removeListener("keypress", this.onKeypress), this.output.write("\n"), 
    v(this.input, !1), this.rl.close(), this.emit(`${this.state}`, this.value), this.unsubscribe();
  }
  restoreCursor() {
    var D = R(this._prevFrame, process.stdout.columns, {
      hard: !0
    }).split("\n").length - 1;
    this.output.write(K.cursor.move(-999, -1 * D));
  }
  render() {
    var D = R(this._render(this) ?? "", process.stdout.columns, {
      hard: !0
    });
    if (D !== this._prevFrame) {
      if ("initial" === this.state) {
        this.output.write(K.cursor.hide);
      } else {
        var e = function aD(D, e) {
          if (D === e) {
            return;
          }
          var r = D.split("\n"), t = e.split("\n"), n = [];
          for (var i = 0; i < Math.max(r.length, t.length); i++) {
            r[i] !== t[i] && n.push(i);
          }
          return n;
        }(this._prevFrame, D);
        if (this.restoreCursor(), e && 1 === e?.length) {
          var r = e[0];
          this.output.write(K.cursor.move(0, r)), this.output.write(K.erase.lines(1));
          var t = D.split("\n");
          this.output.write(t[r]), this._prevFrame = D, this.output.write(K.cursor.move(0, t.length - r - 1));
          return;
        } else if (e && e?.length > 1) {
          var n = e[0];
          this.output.write(K.cursor.move(0, n)), this.output.write(K.erase.down());
          var i = D.split("\n").slice(n);
          this.output.write(i.join("\n")), this._prevFrame = D;
          return;
        }
        this.output.write(K.erase.down());
      }
      this.output.write(D), "initial" === this.state && (this.state = "active"), this._prevFrame = D;
    }
  }
};

class xD extends au {
  get cursor() {
    return this.value ? 0 : 1;
  }
  get _value() {
    return 0 === this.cursor;
  }
  constructor(D) {
    super(D, !1), this.value = !!D.initialValue, this.on("value", (() => {
      this.value = this._value;
    })), this.on("confirm", (D => {
      this.output.write(K.cursor.move(0, -1)), this.value = D, this.state = "submit", 
      this.close();
    })), this.on("cursor", (() => {
      this.value = !this.value;
    }));
  }
}

var ou = Object.defineProperty, MD = (D, e, r) => (((D, e, r) => {
  e in D ? ou(D, e, {
    enumerable: !0,
    configurable: !0,
    writable: !0,
    value: r
  }) : D[e] = r;
})(D, e + "", r), r);

class TD extends au {
  constructor(D) {
    super(D), MD(this, "valueWithCursor", ""), this.on("finalize", (() => {
      this.value || (this.value = D.defaultValue), this.valueWithCursor = this.value;
    })), this.on("value", (() => {
      if (this.cursor >= this.value.length) {
        this.valueWithCursor = `${this.value}${Y.inverse(Y.hidden("_"))}`;
      } else {
        var D = this.value.slice(0, this.cursor), e = this.value.slice(this.cursor);
        this.valueWithCursor = `${D}${Y.inverse(e[0])}${e.slice(1)}`;
      }
    }));
  }
  get cursor() {
    return this._cursor;
  }
}

var su = globalThis.process.platform.startsWith("win");

var cu = function q() {
  return "win32" !== D.platform ? "linux" !== D.env.TERM : Boolean(D.env.CI) || Boolean(D.env.WT_SESSION) || Boolean(D.env.TERMINUS_SUBLIME) || "{cmd::Cmder}" === D.env.ConEmuTask || "Terminus-Sublime" === D.env.TERM_PROGRAM || "vscode" === D.env.TERM_PROGRAM || "xterm-256color" === D.env.TERM || "alacritty" === D.env.TERM || "JetBrains-JediTerm" === D.env.TERMINAL_EMULATOR;
}(), o = (D, e) => cu ? D : e, Fu = o("◆", "*"), lu = o("■", "x"), du = o("▲", "x"), Cu = o("◇", "o"), pu = o("┌", "T"), Eu = o("│", "|"), fu = o("└", "—"), hu = o("●", ">"), vu = o("○", " "), y = D => {
  switch (D) {
   case "initial":
   case "active":
    return Y.cyan(Fu);

   case "cancel":
    return Y.red(lu);

   case "error":
    return Y.yellow(du);

   case "submit":
    return Y.green(Cu);
  }
}, te = D => new TD({
  validate: D.validate,
  placeholder: D.placeholder,
  defaultValue: D.defaultValue,
  initialValue: D.initialValue,
  render() {
    var e = `${Y.gray(Eu)}\n${y(this.state)}  ${D.message}\n`, r = D.placeholder ? Y.inverse(D.placeholder[0]) + Y.dim(D.placeholder.slice(1)) : Y.inverse(Y.hidden("_")), t = this.value ? this.valueWithCursor : r;
    switch (this.state) {
     case "error":
      return `${e.trim()}\n${Y.yellow(Eu)}  ${t}\n${Y.yellow(fu)}  ${Y.yellow(this.error)}\n`;

     case "submit":
      return `${e}${Y.gray(Eu)}  ${Y.dim(this.value || D.placeholder)}`;

     case "cancel":
      return `${e}${Y.gray(Eu)}  ${Y.strikethrough(Y.dim(this.value ?? ""))}${this.value?.trim() ? "\n" + Y.gray(Eu) : ""}`;

     default:
      return `${e}${Y.cyan(Eu)}  ${t}\n${Y.cyan(fu)}\n`;
    }
  }
}).prompt(), se = D => {
  var e = D.active ?? "Yes", r = D.inactive ?? "No";
  return new xD({
    active: e,
    inactive: r,
    initialValue: D.initialValue ?? !0,
    render() {
      var t = `${Y.gray(Eu)}\n${y(this.state)}  ${D.message}\n`, n = this.value ? e : r;
      switch (this.state) {
       case "submit":
        return `${t}${Y.gray(Eu)}  ${Y.dim(n)}`;

       case "cancel":
        return `${t}${Y.gray(Eu)}  ${Y.strikethrough(Y.dim(n))}\n${Y.gray(Eu)}`;

       default:
        return `${t}${Y.cyan(Eu)}  ${this.value ? `${Y.green(hu)} ${e}` : `${Y.dim(vu)} ${Y.dim(e)}`} ${Y.dim("/")} ${this.value ? `${Y.dim(vu)} ${Y.dim(r)}` : `${Y.green(hu)} ${r}`}\n${Y.cyan(fu)}\n`;
      }
    }
  }).prompt();
}, ue = (D = "") => {
  process.stdout.write(`${Y.gray(fu)}  ${Y.red(D)}\n\n`);
}, de = () => {
  var D = cu ? [ "◒", "◐", "◓", "◑" ] : [ "•", "o", "O", "0" ], n = cu ? 80 : 120;
  var i, a, s = !1, c = "";
  var u = (D = "", e = 0) => {
    c = D ?? c, s = !1, clearInterval(a);
    var r = 0 === e ? Y.green(Cu) : 1 === e ? Y.red(lu) : Y.red(du);
    process.stdout.write(K.cursor.move(-999, 0)), process.stdout.write(K.erase.down(1)), 
    process.stdout.write(`${r}  ${c}\n`), i();
  }, $ = D => {
    s && u(D > 1 ? "Something went wrong" : "Canceled", D);
  };
  return process.on("uncaughtExceptionMonitor", (() => $(2))), process.on("unhandledRejection", (() => $(2))), 
  process.on("SIGINT", (() => $(1))), process.on("SIGTERM", (() => $(1))), process.on("exit", $), 
  {
    start: (l = "") => {
      s = !0, i = function WD({input: D = e, output: n = r, overwrite: i = !0, hideCursor: a = !0} = {}) {
        var s = t.createInterface({
          input: D,
          output: n,
          prompt: "",
          tabSize: 1
        });
        t.emitKeypressEvents(D, s), D.isTTY && D.setRawMode(!0);
        var C = (e, {name: r}) => {
          if ("" === String(e) && process.exit(0), !i) {
            return;
          }
          t.moveCursor(n, "return" === r ? 0 : -1, "return" === r ? -1 : 0, (() => {
            t.clearLine(n, 1, (() => {
              D.once("keypress", C);
            }));
          }));
        };
        return a && process.stdout.write(K.cursor.hide), D.once("keypress", C), () => {
          D.off("keypress", C), a && process.stdout.write(K.cursor.show), D.isTTY && !su && D.setRawMode(!1), 
          s.terminal = !1, s.close();
        };
      }(), c = l.replace(/\.+$/, ""), process.stdout.write(`${Y.gray(Eu)}\n`);
      var d = 0, p = 0;
      a = setInterval((() => {
        var e = Y.magenta(D[d]), r = ".".repeat(Math.floor(p)).slice(0, 3);
        process.stdout.write(K.cursor.move(-999, 0)), process.stdout.write(K.erase.down(1)), 
        process.stdout.write(`${e}  ${c}${r}`), d = d + 1 < D.length ? d + 1 : 0, p = p < D.length ? p + .125 : 0;
      }), n);
    },
    stop: u,
    message: (D = "") => {
      c = D ?? c;
    }
  };
};

var mu = {
  exports: {}
};

var gu;

var Bu;

var bu;

var yu;

var Au;

if ("win32" === process.platform || global.TESTING_WINDOWS) {
  Au = function requireWindows() {
    if (Bu) {
      return gu;
    }
    Bu = 1;
    gu = isexe;
    isexe.sync = function sync(e, r) {
      return checkStat(D.statSync(e), e, r);
    };
    var D = p;
    function checkStat(D, e, r) {
      if (!D.isSymbolicLink() && !D.isFile()) {
        return !1;
      }
      return function checkPathExt(D, e) {
        var r = void 0 !== e.pathExt ? e.pathExt : process.env.PATHEXT;
        if (!r) {
          return !0;
        }
        if (-1 !== (r = r.split(";")).indexOf("")) {
          return !0;
        }
        for (var t = 0; t < r.length; t++) {
          var n = r[t].toLowerCase();
          if (n && D.substr(-n.length).toLowerCase() === n) {
            return !0;
          }
        }
        return !1;
      }(e, r);
    }
    function isexe(e, r, t) {
      D.stat(e, (function(D, n) {
        t(D, D ? !1 : checkStat(n, e, r));
      }));
    }
    return gu;
  }();
} else {
  Au = function requireMode() {
    if (yu) {
      return bu;
    }
    yu = 1;
    bu = isexe;
    isexe.sync = function sync(e, r) {
      return checkStat(D.statSync(e), r);
    };
    var D = p;
    function isexe(e, r, t) {
      D.stat(e, (function(D, e) {
        t(D, D ? !1 : checkStat(e, r));
      }));
    }
    function checkStat(D, e) {
      return D.isFile() && function checkMode(D, e) {
        var r = D.mode;
        var t = D.uid;
        var n = D.gid;
        var i = void 0 !== e.uid ? e.uid : process.getuid && process.getuid();
        var a = void 0 !== e.gid ? e.gid : process.getgid && process.getgid();
        var s = parseInt("100", 8);
        var c = parseInt("010", 8);
        return r & parseInt("001", 8) || r & c && n === a || r & s && t === i || r & (s | c) && 0 === i;
      }(D, e);
    }
    return bu;
  }();
}

var wu = isexe$1;

isexe$1.sync = function sync(D, e) {
  try {
    return Au.sync(D, e || {});
  } catch (D) {
    if (e && e.ignoreErrors || "EACCES" === D.code) {
      return !1;
    } else {
      throw D;
    }
  }
};

function isexe$1(D, e, r) {
  if ("function" == typeof e) {
    r = e;
    e = {};
  }
  if (!r) {
    if ("function" != typeof Promise) {
      throw new TypeError("callback not provided");
    }
    return new Promise((function(r, t) {
      isexe$1(D, e || {}, (function(D, e) {
        if (D) {
          t(D);
        } else {
          r(e);
        }
      }));
    }));
  }
  Au(D, e || {}, (function(D, t) {
    if (D) {
      if ("EACCES" === D.code || e && e.ignoreErrors) {
        D = null;
        t = !1;
      }
    }
    r(D, t);
  }));
}

var xu = "win32" === process.platform || "cygwin" === process.env.OSTYPE || "msys" === process.env.OSTYPE;

var Su = E;

var $u = xu ? ";" : ":";

var Tu = wu;

var getNotFoundError = D => Object.assign(new Error(`not found: ${D}`), {
  code: "ENOENT"
});

var getPathInfo = (D, e) => {
  var r = e.colon || $u;
  var t = D.match(/\//) || xu && D.match(/\\/) ? [ "" ] : [ ...xu ? [ process.cwd() ] : [], ...(e.path || process.env.PATH || "").split(r) ];
  var n = xu ? e.pathExt || process.env.PATHEXT || ".EXE;.CMD;.BAT;.COM" : "";
  var i = xu ? n.split(r) : [ "" ];
  if (xu) {
    if (-1 !== D.indexOf(".") && "" !== i[0]) {
      i.unshift("");
    }
  }
  return {
    pathEnv: t,
    pathExt: i,
    pathExtExe: n
  };
};

var which$1 = (D, e, r) => {
  if ("function" == typeof e) {
    r = e;
    e = {};
  }
  if (!e) {
    e = {};
  }
  var {pathEnv: t, pathExt: n, pathExtExe: i} = getPathInfo(D, e);
  var a = [];
  var step = r => new Promise(((n, i) => {
    if (r === t.length) {
      return e.all && a.length ? n(a) : i(getNotFoundError(D));
    }
    var s = t[r];
    var c = /^".*"$/.test(s) ? s.slice(1, -1) : s;
    var l = Su.join(c, D);
    var d = !c && /^\.[\\\/]/.test(D) ? D.slice(0, 2) + l : l;
    n(subStep(d, r, 0));
  }));
  var subStep = (D, r, t) => new Promise(((s, c) => {
    if (t === n.length) {
      return s(step(r + 1));
    }
    var l = n[t];
    Tu(D + l, {
      pathExt: i
    }, ((n, i) => {
      if (!n && i) {
        if (e.all) {
          a.push(D + l);
        } else {
          return s(D + l);
        }
      }
      return s(subStep(D, r, t + 1));
    }));
  }));
  return r ? step(0).then((D => r(null, D)), r) : step(0);
};

var Iu = which$1;

which$1.sync = (D, e) => {
  e = e || {};
  var {pathEnv: r, pathExt: t, pathExtExe: n} = getPathInfo(D, e);
  var i = [];
  for (var a = 0; a < r.length; a++) {
    var s = r[a];
    var c = /^".*"$/.test(s) ? s.slice(1, -1) : s;
    var l = Su.join(c, D);
    var d = !c && /^\.[\\\/]/.test(D) ? D.slice(0, 2) + l : l;
    for (var p = 0; p < t.length; p++) {
      var E = d + t[p];
      try {
        if (Tu.sync(E, {
          pathExt: n
        })) {
          if (e.all) {
            i.push(E);
          } else {
            return E;
          }
        }
      } catch (D) {}
    }
  }
  if (e.all && i.length) {
    return i;
  }
  if (e.nothrow) {
    return null;
  }
  throw getNotFoundError(D);
};

var ku = {
  exports: {}
};

var pathKey$1 = (D = {}) => {
  var e = D.env || process.env;
  if ("win32" !== (D.platform || process.platform)) {
    return "PATH";
  }
  return Object.keys(e).reverse().find((D => "PATH" === D.toUpperCase())) || "Path";
};

ku.exports = pathKey$1;

ku.exports.default = pathKey$1;

var Ou = E;

var ju = Iu;

var Pu = ku.exports;

function resolveCommandAttempt(D, e) {
  var r = D.options.env || process.env;
  var t = process.cwd();
  var n = null != D.options.cwd;
  var i = n && void 0 !== process.chdir && !process.chdir.disabled;
  if (i) {
    try {
      process.chdir(D.options.cwd);
    } catch (D) {}
  }
  var a;
  try {
    a = ju.sync(D.command, {
      path: r[Pu({
        env: r
      })],
      pathExt: e ? Ou.delimiter : void 0
    });
  } catch (D) {} finally {
    if (i) {
      process.chdir(t);
    }
  }
  if (a) {
    a = Ou.resolve(n ? D.options.cwd : "", a);
  }
  return a;
}

var Gu = function resolveCommand$1(D) {
  return resolveCommandAttempt(D) || resolveCommandAttempt(D, !0);
};

var Ru = {};

var Lu = /([()\][%!^"`<>&|;, *?])/g;

Ru.command = function escapeCommand(D) {
  return D = D.replace(Lu, "^$1");
};

Ru.argument = function escapeArgument(D, e) {
  D = (D = `"${D = (D = (D = `${D}`).replace(/(\\*)"/g, '$1$1\\"')).replace(/(\\*)$/, "$1$1")}"`).replace(Lu, "^$1");
  if (e) {
    D = D.replace(Lu, "^$1");
  }
  return D;
};

var Mu = /^#!(.*)/;

var _u = p;

var shebangCommand = (D = "") => {
  var e = D.match(Mu);
  if (!e) {
    return null;
  }
  var [r, t] = e[0].replace(/#! ?/, "").split(" ");
  var n = r.split("/").pop();
  if ("env" === n) {
    return t;
  }
  return t ? `${n} ${t}` : n;
};

var Nu = E;

var Wu = Gu;

var Uu = Ru;

var zu = function readShebang$1(D) {
  var e = Buffer.alloc(150);
  var r;
  try {
    r = _u.openSync(D, "r");
    _u.readSync(r, e, 0, 150, 0);
    _u.closeSync(r);
  } catch (D) {}
  return shebangCommand(e.toString());
};

var Ku = "win32" === process.platform;

var Vu = /\.(?:com|exe)$/i;

var qu = /node_modules[\\/].bin[\\/][^\\/]+\.cmd$/i;

function parseNonShell(D) {
  if (!Ku) {
    return D;
  }
  var e = function detectShebang(D) {
    D.file = Wu(D);
    var e = D.file && zu(D.file);
    if (e) {
      D.args.unshift(D.file);
      D.command = e;
      return Wu(D);
    }
    return D.file;
  }(D);
  var r = !Vu.test(e);
  if (D.options.forceShell || r) {
    var t = qu.test(e);
    D.command = Nu.normalize(D.command);
    D.command = Uu.command(D.command);
    D.args = D.args.map((D => Uu.argument(D, t)));
    var n = [ D.command ].concat(D.args).join(" ");
    D.args = [ "/d", "/s", "/c", `"${n}"` ];
    D.command = process.env.comspec || "cmd.exe";
    D.options.windowsVerbatimArguments = !0;
  }
  return D;
}

var Hu = "win32" === process.platform;

function notFoundError(D, e) {
  return Object.assign(new Error(`${e} ${D.command} ENOENT`), {
    code: "ENOENT",
    errno: "ENOENT",
    syscall: `${e} ${D.command}`,
    path: D.command,
    spawnargs: D.args
  });
}

function verifyENOENT(D, e) {
  if (Hu && 1 === D && !e.file) {
    return notFoundError(e.original, "spawn");
  }
  return null;
}

var Yu = {
  hookChildProcess: function hookChildProcess(D, e) {
    if (!Hu) {
      return;
    }
    var r = D.emit;
    D.emit = function(t, n) {
      if ("exit" === t) {
        var i = verifyENOENT(n, e);
        if (i) {
          return r.call(D, "error", i);
        }
      }
      return r.apply(D, arguments);
    };
  },
  verifyENOENT,
  verifyENOENTSync: function verifyENOENTSync(D, e) {
    if (Hu && 1 === D && !e.file) {
      return notFoundError(e.original, "spawnSync");
    }
    return null;
  },
  notFoundError
};

var Ju = f;

var Xu = function parse$1(D, e, r) {
  if (e && !Array.isArray(e)) {
    r = e;
    e = null;
  }
  var t = {
    command: D,
    args: e = e ? e.slice(0) : [],
    options: r = Object.assign({}, r),
    file: void 0,
    original: {
      command: D,
      args: e
    }
  };
  return r.shell ? t : parseNonShell(t);
};

var Zu = Yu;

function spawn(D, e, r) {
  var t = Xu(D, e, r);
  var n = Ju.spawn(t.command, t.args, t.options);
  Zu.hookChildProcess(n, t);
  return n;
}

mu.exports = spawn;

mu.exports.spawn = spawn;

mu.exports.sync = function spawnSync(D, e, r) {
  var t = Xu(D, e, r);
  var n = Ju.spawnSync(t.command, t.args, t.options);
  n.error = n.error || Zu.verifyENOENTSync(n.status, t);
  return n;
};

mu.exports._parse = Xu;

mu.exports._enoent = Zu;

var Qu = getDefaultExportFromCjs(mu.exports);

function pathKey(D = {}) {
  var {env: e = process.env, platform: r = process.platform} = D;
  if ("win32" !== r) {
    return "PATH";
  }
  return Object.keys(e).reverse().find((D => "PATH" === D.toUpperCase())) || "Path";
}

var applyPreferLocal = (D, e) => {
  var r;
  while (r !== e) {
    D.push(s.join(e, "node_modules/.bin"));
    r = e;
    e = s.resolve(e, "..");
  }
};

var applyExecPath = (D, e, r) => {
  var t = e instanceof URL ? h(e) : e;
  D.push(s.resolve(r, t, ".."));
};

var npmRunPathEnv = ({env: e = D.env, ...r} = {}) => {
  var t = pathKey({
    env: e = {
      ...e
    }
  });
  r.path = e[t];
  e[t] = (({cwd: e = D.cwd(), path: r = D.env[pathKey()], preferLocal: t = !0, execPath: n = D.execPath, addExecPath: i = !0} = {}) => {
    var a = e instanceof URL ? h(e) : e;
    var c = s.resolve(a);
    var l = [];
    if (t) {
      applyPreferLocal(l, c);
    }
    if (i) {
      applyExecPath(l, n, c);
    }
    return [ ...l, r ].join(s.delimiter);
  })(r);
  return e;
};

var copyProperty = (D, e, r, t) => {
  if ("length" === r || "prototype" === r) {
    return;
  }
  if ("arguments" === r || "caller" === r) {
    return;
  }
  var n = Object.getOwnPropertyDescriptor(D, r);
  var i = Object.getOwnPropertyDescriptor(e, r);
  if (!canCopyProperty(n, i) && t) {
    return;
  }
  Object.defineProperty(D, r, i);
};

var canCopyProperty = function(D, e) {
  return void 0 === D || D.configurable || D.writable === e.writable && D.enumerable === e.enumerable && D.configurable === e.configurable && (D.writable || D.value === e.value);
};

var wrappedToString = (D, e) => `/* Wrapped ${D}*/\n${e}`;

var uD = Object.getOwnPropertyDescriptor(Function.prototype, "toString");

var DD = Object.getOwnPropertyDescriptor(Function.prototype.toString, "name");

function mimicFunction(D, e, {ignoreNonConfigurable: r = !1} = {}) {
  var {name: t} = D;
  for (var n of Reflect.ownKeys(e)) {
    copyProperty(D, e, n, r);
  }
  ((D, e) => {
    var r = Object.getPrototypeOf(e);
    if (r === Object.getPrototypeOf(D)) {
      return;
    }
    Object.setPrototypeOf(D, r);
  })(D, e);
  ((D, e, r) => {
    var t = "" === r ? "" : `with ${r.trim()}() `;
    var n = wrappedToString.bind(null, t, e.toString());
    Object.defineProperty(n, "name", DD);
    Object.defineProperty(D, "toString", {
      ...uD,
      value: n
    });
  })(D, e, t);
  return D;
}

var eD = new WeakMap;

var onetime = (D, e = {}) => {
  if ("function" != typeof D) {
    throw new TypeError("Expected a function");
  }
  var r;
  var t = 0;
  var n = D.displayName || D.name || "<anonymous>";
  var onetime = function(...i) {
    eD.set(onetime, ++t);
    if (1 === t) {
      r = D.apply(this, i);
      D = null;
    } else if (!0 === e.throw) {
      throw new Error(`Function \`${n}\` can only be called once`);
    }
    return r;
  };
  mimicFunction(onetime, D);
  eD.set(onetime, t);
  return onetime;
};

onetime.callCount = D => {
  if (!eD.has(D)) {
    throw new Error(`The given function \`${D.name}\` is not wrapped by the \`onetime\` package`);
  }
  return eD.get(D);
};

var getRealtimeSignal = (D, e) => ({
  name: `SIGRT${e + 1}`,
  number: rD + e,
  action: "terminate",
  description: "Application-specific signal (realtime)",
  standard: "posix"
});

var rD = 34;

var nD = 64;

var iD = [ {
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
  var D = Array.from({
    length: nD - rD + 1
  }, getRealtimeSignal);
  return [ ...iD, ...D ].map(normalizeSignal);
};

var normalizeSignal = ({name: D, number: e, description: r, action: t, forced: n = !1, standard: i}) => {
  var {signals: {[D]: a}} = g;
  var s = void 0 !== a;
  return {
    name: D,
    number: s ? a : e,
    description: r,
    supported: s,
    action: t,
    forced: n,
    standard: i
  };
};

var getSignalByName = ({name: D, number: e, description: r, supported: t, action: n, forced: i, standard: a}) => [ D, {
  name: D,
  number: e,
  description: r,
  supported: t,
  action: n,
  forced: i,
  standard: a
} ];

var oD = (() => {
  var D = getSignals();
  return Object.fromEntries(D.map(getSignalByName));
})();

var getSignalByNumber = (D, e) => {
  var r = findSignalByNumber(D, e);
  if (void 0 === r) {
    return {};
  }
  var {name: t, description: n, supported: i, action: a, forced: s, standard: c} = r;
  return {
    [D]: {
      name: t,
      number: D,
      description: n,
      supported: i,
      action: a,
      forced: s,
      standard: c
    }
  };
};

var findSignalByNumber = (D, e) => {
  var r = e.find((({name: e}) => g.signals[e] === D));
  if (void 0 !== r) {
    return r;
  }
  return e.find((e => e.number === D));
};

(() => {
  var D = getSignals();
  var e = Array.from({
    length: nD + 1
  }, ((e, r) => getSignalByNumber(r, D)));
  Object.assign({}, ...e);
})();

var makeError = ({stdout: e, stderr: r, all: t, error: n, signal: i, exitCode: a, command: s, escapedCommand: c, timedOut: l, isCanceled: d, killed: p, parsed: {options: {timeout: E, cwd: f = D.cwd()}}}) => {
  var h = void 0 === (i = null === i ? void 0 : i) ? void 0 : oD[i].description;
  var m = (({timedOut: D, timeout: e, errorCode: r, signal: t, signalDescription: n, exitCode: i, isCanceled: a}) => {
    if (D) {
      return `timed out after ${e} milliseconds`;
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
  var w = [ b, r, e ].filter(Boolean).join("\n");
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
  n.stdout = e;
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

var sD = [ "stdin", "stdout", "stderr" ];

var normalizeStdio = D => {
  if (!D) {
    return;
  }
  var {stdio: e} = D;
  if (void 0 === e) {
    return sD.map((e => D[e]));
  }
  if ((D => sD.some((e => void 0 !== D[e])))(D)) {
    throw new Error(`It's not possible to provide \`stdio\` in combination with one of ${sD.map((D => `\`${D}\``)).join(", ")}`);
  }
  if ("string" == typeof e) {
    return e;
  }
  if (!Array.isArray(e)) {
    throw new TypeError(`Expected \`stdio\` to be of type \`string\` or \`Array\`, got \`${typeof e}\``);
  }
  var r = Math.max(e.length, sD.length);
  return Array.from({
    length: r
  }, ((D, r) => e[r]));
};

var cD = [];

cD.push("SIGHUP", "SIGINT", "SIGTERM");

if ("win32" !== process.platform) {
  cD.push("SIGALRM", "SIGABRT", "SIGVTALRM", "SIGXCPU", "SIGXFSZ", "SIGUSR2", "SIGTRAP", "SIGSYS", "SIGQUIT", "SIGIOT");
}

if ("linux" === process.platform) {
  cD.push("SIGIO", "SIGPOLL", "SIGPWR", "SIGSTKFLT");
}

var processOk = D => !!D && "object" == typeof D && "function" == typeof D.removeListener && "function" == typeof D.emit && "function" == typeof D.reallyExit && "function" == typeof D.listeners && "function" == typeof D.kill && "number" == typeof D.pid && "function" == typeof D.on;

var FD = Symbol.for("signal-exit emitter");

var lD = globalThis;

var dD = Object.defineProperty.bind(Object);

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
    if (lD[FD]) {
      return lD[FD];
    }
    dD(lD, FD, {
      value: this,
      writable: !1,
      enumerable: !1,
      configurable: !1
    });
  }
  on(D, e) {
    this.listeners[D].push(e);
  }
  removeListener(D, e) {
    var r = this.listeners[D];
    var t = r.indexOf(e);
    if (-1 === t) {
      return;
    }
    if (0 === t && 1 === r.length) {
      r.length = 0;
    } else {
      r.splice(t, 1);
    }
  }
  emit(D, e, r) {
    if (this.emitted[D]) {
      return !1;
    }
    this.emitted[D] = !0;
    var t = !1;
    for (var n of this.listeners[D]) {
      t = !0 === n(e, r) || t;
    }
    if ("exit" === D) {
      t = this.emit("afterExit", e, r) || t;
    }
    return t;
  }
}

class SignalExitBase {}

var CD = globalThis.process;

var {onExit: pD} = (fD = processOk(CD) ? new class SignalExit extends SignalExitBase {
  #u="win32" === CD.platform ? "SIGINT" : "SIGHUP";
  #D=new Emitter;
  #e;
  #r;
  #t;
  #n={};
  #i=!1;
  constructor(D) {
    var e;
    super();
    e = this;
    this.#e = D;
    this.#n = {};
    var _loop = function(r) {
      e.#n[r] = () => {
        var t = e.#e.listeners(r);
        var {count: n} = e.#D;
        if ("object" == typeof D.__signal_exit_emitter__ && "number" == typeof D.__signal_exit_emitter__.count) {
          n += D.__signal_exit_emitter__.count;
        }
        if (t.length === n) {
          e.unload();
          var i = e.#D.emit("exit", null, r);
          var a = "SIGHUP" === r ? e.#u : r;
          if (!i) {
            D.kill(D.pid, a);
          }
        }
      };
    };
    for (var r of cD) {
      _loop(r);
    }
    this.#t = D.reallyExit;
    this.#r = D.emit;
  }
  onExit(D, e) {
    if (!processOk(this.#e)) {
      return () => {};
    }
    if (!1 === this.#i) {
      this.load();
    }
    var r = e?.alwaysLast ? "afterExit" : "exit";
    this.#D.on(r, D);
    return () => {
      this.#D.removeListener(r, D);
      if (0 === this.#D.listeners.exit.length && 0 === this.#D.listeners.afterExit.length) {
        this.unload();
      }
    };
  }
  load() {
    if (this.#i) {
      return;
    }
    this.#i = !0;
    this.#D.count += 1;
    for (var D of cD) {
      try {
        var e = this.#n[D];
        if (e) {
          this.#e.on(D, e);
        }
      } catch (D) {}
    }
    this.#e.emit = (D, ...e) => this.#a(D, ...e);
    this.#e.reallyExit = D => this.#o(D);
  }
  unload() {
    if (!this.#i) {
      return;
    }
    this.#i = !1;
    cD.forEach((D => {
      var e = this.#n[D];
      if (!e) {
        throw new Error("Listener not defined for signal: " + D);
      }
      try {
        this.#e.removeListener(D, e);
      } catch (D) {}
    }));
    this.#e.emit = this.#r;
    this.#e.reallyExit = this.#t;
    this.#D.count -= 1;
  }
  #o(D) {
    if (!processOk(this.#e)) {
      return 0;
    }
    this.#e.exitCode = D || 0;
    this.#D.emit("exit", this.#e.exitCode, null);
    return this.#t.call(this.#e, this.#e.exitCode);
  }
  #a(D, ...e) {
    var r = this.#r;
    if ("exit" === D && processOk(this.#e)) {
      if ("number" == typeof e[0]) {
        this.#e.exitCode = e[0];
      }
      var t = r.call(this.#e, D, ...e);
      this.#D.emit("exit", this.#e.exitCode, null);
      return t;
    } else {
      return r.call(this.#e, D, ...e);
    }
  }
}(CD) : new class SignalExitFallback extends SignalExitBase {
  onExit() {
    return () => {};
  }
  load() {}
  unload() {}
}, {
  onExit: (D, e) => fD.onExit(D, e),
  load: () => fD.load(),
  unload: () => fD.unload()
});

var fD;

var spawnedKill = (D, e = "SIGTERM", r = {}) => {
  var t = D(e);
  setKillTimeout(D, e, r, t);
  return t;
};

var setKillTimeout = (D, e, r, t) => {
  if (!shouldForceKill(e, r, t)) {
    return;
  }
  var n = getForceKillAfterTimeout(r);
  var i = setTimeout((() => {
    D("SIGKILL");
  }), n);
  if (i.unref) {
    i.unref();
  }
};

var shouldForceKill = (D, {forceKillAfterTimeout: e}, r) => isSigterm(D) && !1 !== e && r;

var isSigterm = D => D === m.constants.signals.SIGTERM || "string" == typeof D && "SIGTERM" === D.toUpperCase();

var getForceKillAfterTimeout = ({forceKillAfterTimeout: D = !0}) => {
  if (!0 === D) {
    return 5e3;
  }
  if (!Number.isFinite(D) || D < 0) {
    throw new TypeError(`Expected the \`forceKillAfterTimeout\` option to be a non-negative integer, got \`${D}\` (${typeof D})`);
  }
  return D;
};

var spawnedCancel = (D, e) => {
  if (D.kill()) {
    e.isCanceled = !0;
  }
};

var setupTimeout = (D, {timeout: e, killSignal: r = "SIGTERM"}, t) => {
  if (0 === e || void 0 === e) {
    return t;
  }
  var n;
  var i = new Promise(((t, i) => {
    n = setTimeout((() => {
      ((D, e, r) => {
        D.kill(e);
        r(Object.assign(new Error("Timed out"), {
          timedOut: !0,
          signal: e
        }));
      })(D, r, i);
    }), e);
  }));
  var a = t.finally((() => {
    clearTimeout(n);
  }));
  return Promise.race([ i, a ]);
};

var validateTimeout = ({timeout: D}) => {
  if (void 0 !== D && (!Number.isFinite(D) || D < 0)) {
    throw new TypeError(`Expected the \`timeout\` option to be a non-negative integer, got \`${D}\` (${typeof D})`);
  }
};

var setExitHandler = async (D, {cleanup: e, detached: r}, t) => {
  if (!e || r) {
    return t;
  }
  var n = pD((() => {
    D.kill();
  }));
  return t.finally((() => {
    n();
  }));
};

function isStream(D) {
  return null !== D && "object" == typeof D && "function" == typeof D.pipe;
}

function isWritableStream(D) {
  return isStream(D) && !1 !== D.writable && "function" == typeof D._write && "object" == typeof D._writableState;
}

var pipeToTarget = (D, e, r) => {
  if ("string" == typeof r) {
    D[e].pipe(B(r));
    return D;
  }
  if (isWritableStream(r)) {
    D[e].pipe(r);
    return D;
  }
  if (!(D => D instanceof d && "function" == typeof D.then)(r)) {
    throw new TypeError("The second argument must be a string, a stream or an Execa child process.");
  }
  if (!isWritableStream(r.stdin)) {
    throw new TypeError("The target child process's stdin must be available.");
  }
  D[e].pipe(r.stdin);
  return r;
};

var addPipeMethods = D => {
  if (null !== D.stdout) {
    D.pipeStdout = pipeToTarget.bind(void 0, D, "stdout");
  }
  if (null !== D.stderr) {
    D.pipeStderr = pipeToTarget.bind(void 0, D, "stderr");
  }
  if (void 0 !== D.all) {
    D.pipeAll = pipeToTarget.bind(void 0, D, "all");
  }
};

var getStreamContents = async (D, {init: e, convertChunk: r, getSize: t, truncateChunk: n, addChunk: i, getFinalChunk: a, finalize: s}, {maxBuffer: c = Number.POSITIVE_INFINITY} = {}) => {
  if (!isAsyncIterable(D)) {
    throw new Error("The first argument must be a Readable, a ReadableStream, or an async iterable.");
  }
  var l = e();
  l.length = 0;
  try {
    for await (var d of D) {
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
  } catch (D) {
    D.bufferedData = s(l);
    throw D;
  }
};

var appendFinalChunk = ({state: D, getSize: e, truncateChunk: r, addChunk: t, getFinalChunk: n, maxBuffer: i}) => {
  var a = n(D);
  if (void 0 !== a) {
    appendChunk({
      convertedChunk: a,
      state: D,
      getSize: e,
      truncateChunk: r,
      addChunk: t,
      maxBuffer: i
    });
  }
};

var appendChunk = ({convertedChunk: D, state: e, getSize: r, truncateChunk: t, addChunk: n, maxBuffer: i}) => {
  var a = r(D);
  var s = e.length + a;
  if (s <= i) {
    addNewChunk(D, e, n, s);
    return;
  }
  var c = t(D, i - e.length);
  if (void 0 !== c) {
    addNewChunk(c, e, n, i);
  }
  throw new MaxBufferError;
};

var addNewChunk = (D, e, r, t) => {
  e.contents = r(D, e, t);
  e.length = t;
};

var isAsyncIterable = D => "object" == typeof D && null !== D && "function" == typeof D[Symbol.asyncIterator];

var getChunkType = D => {
  var e = typeof D;
  if ("string" === e) {
    return "string";
  }
  if ("object" !== e || null === D) {
    return "others";
  }
  if (globalThis.Buffer?.isBuffer(D)) {
    return "buffer";
  }
  var r = vD.call(D);
  if ("[object ArrayBuffer]" === r) {
    return "arrayBuffer";
  }
  if ("[object DataView]" === r) {
    return "dataView";
  }
  if (Number.isInteger(D.byteLength) && Number.isInteger(D.byteOffset) && "[object ArrayBuffer]" === vD.call(D.buffer)) {
    return "typedArray";
  }
  return "others";
};

var {toString: vD} = Object.prototype;

class MaxBufferError extends Error {
  name="MaxBufferError";
  constructor() {
    super("maxBuffer exceeded");
  }
}

var throwObjectStream = D => {
  throw new Error(`Streams in object mode are not supported: ${String(D)}`);
};

var getLengthProp = D => D.length;

var mD = new TextEncoder;

var useUint8Array = D => new Uint8Array(D);

var useUint8ArrayWithOffset = D => new Uint8Array(D.buffer, D.byteOffset, D.byteLength);

var resizeArrayBufferSlow = (D, e) => {
  if (e <= D.byteLength) {
    return D;
  }
  var r = new ArrayBuffer(getNewContentsLength(e));
  new Uint8Array(r).set(new Uint8Array(D), 0);
  return r;
};

var resizeArrayBuffer = (D, e) => {
  if (e <= D.maxByteLength) {
    D.resize(e);
    return D;
  }
  var r = new ArrayBuffer(e, {
    maxByteLength: getNewContentsLength(e)
  });
  new Uint8Array(r).set(new Uint8Array(D), 0);
  return r;
};

var getNewContentsLength = D => gD ** Math.ceil(Math.log(D) / Math.log(gD));

var gD = 2;

var hasArrayBufferResize = () => "resize" in ArrayBuffer.prototype;

var BD = {
  init: () => ({
    contents: new ArrayBuffer(0)
  }),
  convertChunk: {
    string: D => mD.encode(D),
    buffer: useUint8Array,
    arrayBuffer: useUint8Array,
    dataView: useUint8ArrayWithOffset,
    typedArray: useUint8ArrayWithOffset,
    others: throwObjectStream
  },
  getSize: getLengthProp,
  truncateChunk: (D, e) => D.slice(0, e),
  addChunk: (D, {contents: e, length: r}, t) => {
    var n = hasArrayBufferResize() ? resizeArrayBuffer(e, t) : resizeArrayBufferSlow(e, t);
    new Uint8Array(n).set(D, r);
    return n;
  },
  getFinalChunk: () => {},
  finalize: ({contents: D, length: e}) => hasArrayBufferResize() ? D : D.slice(0, e)
};

async function getStreamAsBuffer(D, e) {
  if (!("Buffer" in globalThis)) {
    throw new Error("getStreamAsBuffer() is only supported in Node.js");
  }
  try {
    return arrayBufferToNodeBuffer(await async function getStreamAsArrayBuffer(D, e) {
      return getStreamContents(D, BD, e);
    }(D, e));
  } catch (D) {
    if (void 0 !== D.bufferedData) {
      D.bufferedData = arrayBufferToNodeBuffer(D.bufferedData);
    }
    throw D;
  }
}

var arrayBufferToNodeBuffer = D => globalThis.Buffer.from(D);

var useTextDecoder = (D, {textDecoder: e}) => e.decode(D, {
  stream: !0
});

var bD = {
  init: () => ({
    contents: "",
    textDecoder: new TextDecoder
  }),
  convertChunk: {
    string: D => D,
    buffer: useTextDecoder,
    arrayBuffer: useTextDecoder,
    dataView: useTextDecoder,
    typedArray: useTextDecoder,
    others: throwObjectStream
  },
  getSize: getLengthProp,
  truncateChunk: (D, e) => D.slice(0, e),
  addChunk: (D, {contents: e}) => e + D,
  getFinalChunk: ({textDecoder: D}) => {
    var e = D.decode();
    return "" === e ? void 0 : e;
  },
  finalize: ({contents: D}) => D
};

var {PassThrough: yD} = S;

var AD = getDefaultExportFromCjs((function() {
  var D = [];
  var e = new yD({
    objectMode: !0
  });
  e.setMaxListeners(0);
  e.add = add;
  e.isEmpty = function isEmpty() {
    return 0 == D.length;
  };
  e.on("unpipe", remove);
  Array.prototype.slice.call(arguments).forEach(add);
  return e;
  function add(r) {
    if (Array.isArray(r)) {
      r.forEach(add);
      return this;
    }
    D.push(r);
    r.once("end", remove.bind(null, r));
    r.once("error", e.emit.bind(e, "error"));
    r.pipe(e, {
      end: !1
    });
    return this;
  }
  function remove(r) {
    if (!(D = D.filter((function(D) {
      return D !== r;
    }))).length && e.readable) {
      e.end();
    }
  }
}));

var getInput = ({input: D, inputFile: e}) => {
  if ("string" != typeof e) {
    return D;
  }
  (D => {
    if (void 0 !== D) {
      throw new TypeError("The `input` and `inputFile` options cannot be both set.");
    }
  })(D);
  return b(e);
};

var handleInput = (D, e) => {
  var r = getInput(e);
  if (void 0 === r) {
    return;
  }
  if (isStream(r)) {
    r.pipe(D.stdin);
  } else {
    D.stdin.end(r);
  }
};

var makeAllStream = (D, {all: e}) => {
  if (!e || !D.stdout && !D.stderr) {
    return;
  }
  var r = AD();
  if (D.stdout) {
    r.add(D.stdout);
  }
  if (D.stderr) {
    r.add(D.stderr);
  }
  return r;
};

var getBufferedData = async (D, e) => {
  if (!D || void 0 === e) {
    return;
  }
  await w(0);
  D.destroy();
  try {
    return await e;
  } catch (D) {
    return D.bufferedData;
  }
};

var getStreamPromise = (D, {encoding: e, buffer: r, maxBuffer: t}) => {
  if (!D || !r) {
    return;
  }
  if ("utf8" === e || "utf-8" === e) {
    return async function getStreamAsString(D, e) {
      return getStreamContents(D, bD, e);
    }(D, {
      maxBuffer: t
    });
  }
  if (null === e || "buffer" === e) {
    return getStreamAsBuffer(D, {
      maxBuffer: t
    });
  }
  return applyEncoding(D, t, e);
};

var applyEncoding = async (D, e, r) => (await getStreamAsBuffer(D, {
  maxBuffer: e
})).toString(r);

var getSpawnedResult = async ({stdout: D, stderr: e, all: r}, {encoding: t, buffer: n, maxBuffer: i}, a) => {
  var s = getStreamPromise(D, {
    encoding: t,
    buffer: n,
    maxBuffer: i
  });
  var c = getStreamPromise(e, {
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
    }, getBufferedData(D, s), getBufferedData(e, c), getBufferedData(r, l) ]);
  }
};

var wD = (async () => {})().constructor.prototype;

var SD = [ "then", "catch", "finally" ].map((D => [ D, Reflect.getOwnPropertyDescriptor(wD, D) ]));

var mergePromise = (D, e) => {
  var _loop = function(t) {
    var n = "function" == typeof e ? (...D) => Reflect.apply(t.value, e(), D) : t.value.bind(e);
    Reflect.defineProperty(D, r, {
      ...t,
      value: n
    });
  };
  for (var [r, t] of SD) {
    _loop(t);
  }
};

var getSpawnedPromise = D => new Promise(((e, r) => {
  D.on("exit", ((D, r) => {
    e({
      exitCode: D,
      signal: r
    });
  }));
  D.on("error", (D => {
    r(D);
  }));
  if (D.stdin) {
    D.stdin.on("error", (D => {
      r(D);
    }));
  }
}));

var normalizeArgs = (D, e = []) => {
  if (!Array.isArray(e)) {
    return [ D ];
  }
  return [ D, ...e ];
};

var $D = /^[\w.-]+$/;

var joinCommand = (D, e) => normalizeArgs(D, e).join(" ");

var getEscapedCommand = (D, e) => normalizeArgs(D, e).map((D => (D => {
  if ("string" != typeof D || $D.test(D)) {
    return D;
  }
  return `"${D.replaceAll('"', '\\"')}"`;
})(D))).join(" ");

var ID = I("execa").enabled;

var padField = (D, e) => String(D).padStart(e, "0");

var logCommand = (e, {verbose: r}) => {
  if (!r) {
    return;
  }
  D.stderr.write(`[${t = new Date, `${padField(t.getHours(), 2)}:${padField(t.getMinutes(), 2)}:${padField(t.getSeconds(), 2)}.${padField(t.getMilliseconds(), 3)}`}] ${e}\n`);
  var t;
};

var handleArguments = (e, r, t = {}) => {
  var n = Qu._parse(e, r, t);
  e = n.command;
  r = n.args;
  (t = {
    maxBuffer: 1e8,
    buffer: !0,
    stripFinalNewline: !0,
    extendEnv: !0,
    preferLocal: !1,
    localDir: (t = n.options).cwd || D.cwd(),
    execPath: D.execPath,
    encoding: "utf8",
    reject: !0,
    cleanup: !0,
    all: !1,
    windowsHide: !0,
    verbose: ID,
    ...t
  }).env = (({env: e, extendEnv: r, preferLocal: t, localDir: n, execPath: i}) => {
    var a = r ? {
      ...D.env,
      ...e
    } : e;
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
  if ("win32" === D.platform && "cmd" === s.basename(e, ".exe")) {
    r.unshift("/q");
  }
  return {
    file: e,
    args: r,
    options: t,
    parsed: n
  };
};

var handleOutput = (D, e, r) => {
  if ("string" != typeof e && !c.isBuffer(e)) {
    return void 0 === r ? void 0 : "";
  }
  if (D.stripFinalNewline) {
    return function stripFinalNewline(D) {
      var e = "string" == typeof D ? "\n" : "\n".charCodeAt();
      var r = "string" == typeof D ? "\r" : "\r".charCodeAt();
      if (D[D.length - 1] === e) {
        D = D.slice(0, -1);
      }
      if (D[D.length - 1] === r) {
        D = D.slice(0, -1);
      }
      return D;
    }(e);
  }
  return e;
};

function execa(D, e, r) {
  var t = handleArguments(D, e, r);
  var n = joinCommand(D, e);
  var i = getEscapedCommand(D, e);
  logCommand(i, t.options);
  validateTimeout(t.options);
  var a;
  try {
    a = l.spawn(t.file, t.args, t.options);
  } catch (D) {
    var s = new l.ChildProcess;
    var c = Promise.reject(makeError({
      error: D,
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
    mergePromise(s, c);
    return s;
  }
  var d = getSpawnedPromise(a);
  var p = setupTimeout(a, t.options, d);
  var E = setExitHandler(a, t.options, p);
  a.kill = spawnedKill.bind(null, a.kill.bind(a));
  a.cancel = spawnedCancel.bind(null, a, {
    isCanceled: !1
  });
  var f = onetime((async () => {
    var [{error: D, exitCode: e, signal: r, timedOut: s}, c, l, d] = await getSpawnedResult(a, t.options, E);
    var p = handleOutput(t.options, c);
    var f = handleOutput(t.options, l);
    var h = handleOutput(t.options, d);
    if (D || 0 !== e || null !== r) {
      var m = makeError({
        error: D,
        exitCode: e,
        signal: r,
        stdout: p,
        stderr: f,
        all: h,
        command: n,
        escapedCommand: i,
        parsed: t,
        timedOut: s,
        isCanceled: t.options.signal ? t.options.signal.aborted : !1,
        killed: a.killed
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
  handleInput(a, t.options);
  a.all = makeAllStream(a, t.options);
  addPipeMethods(a);
  mergePromise(a, f);
  return a;
}

async function run(D) {
  var e = de();
  ((D = "") => {
    process.stdout.write(`${Y.gray(pu)}  ${D}\n`);
  })("GQL.Tada");
  var r = await question("Where can we get your schema? Point us at an introspection JSON-file, a GraphQL schema file or an endpoint", (async r => {
    try {
      var t = new URL(r);
      e.start("Validating the URL.");
      try {
        var n = await fetch(t.toString());
        if (!n.ok) {
          e.stop("Validated the URL.");
          return !!await se({
            message: `Got ${n.status} from ${t.toString()}, continue anyway? You can add headers later.`
          });
        }
      } catch (D) {
        e.stop("Validated the URL.");
        return !!await se({
          message: `Got ${D.message} from ${t.toString()}, continue anyway? You can add headers later.`
        });
      }
      e.stop("Validated the URL.");
      return !0;
    } catch (D) {}
    if (!(r.endsWith(".json") || r.endsWith(".graphql"))) {
      return !1;
    }
    var i = s.resolve(D, r);
    var c = !!await a.readFile(i);
    if (!c) {
      console.log(`\nCould not find "${i}"`);
    }
    return c;
  }));
  var t = await question("What directory do you want us to write the tadaOutputFile to?", (async e => {
    var r = s.resolve(D, e);
    var t = !!await a.stat(r);
    if (!t) {
      console.log(`\nCould not find "${r}"`);
    }
    return t;
  }));
  if (hD(t)) {
    ue("Operation cancelled.");
    process.exit(0);
  }
  t = s.resolve(t, "graphql-env.d.ts");
  var n = await se({
    message: "Do you want us to install the dependencies?"
  });
  if (hD(n)) {
    ue("Operation cancelled.");
    process.exit(0);
  }
  var i = !1;
  var c;
  try {
    var l = s.resolve(D, "package.json");
    var d = await a.readFile(l, "utf-8");
    c = JSON.parse(d);
    var p = Object.entries({
      ...c.dependencies,
      ...c.devDependencies
    }).find((D => "typescript" === D[0]));
    if (p && "string" == typeof p[1]) {
      i = k(p[1], O.typescript_embed_lsp);
    }
  } catch (D) {}
  if (n) {
    e.start("Installing packages.");
    await async function installPackages(D, e, r) {
      if (r) {
        await execa(D, [ "yarn" === D ? "add" : "install", "-D", "@0no-co/graphqlsp" ], {
          stdio: "ignore",
          cwd: e
        });
      }
      await execa(D, [ "yarn" === D ? "add" : "install", "gql.tada" ], {
        stdio: "ignore",
        cwd: e
      });
    }(function getPkgManager() {
      var D = process.env.npm_config_user_agent || "";
      if (D.startsWith("yarn")) {
        return "yarn";
      }
      if (D.startsWith("pnpm")) {
        return "pnpm";
      }
      return "npm";
    }(), D, !i);
    e.stop("Installed packages.");
  } else {
    e.start("Writing to package.json.");
    try {
      var E = s.resolve(D, "package.json");
      var f = await a.readFile(E, "utf-8");
      if (!(c = JSON.parse(f)).dependencies) {
        c.dependencies = {};
      }
      if (!c.dependencies["gql.tada"]) {
        c.dependencies["gql.tada"] = "^1.4.3";
      }
      if (!i) {
        if (!c.devDependencies) {
          c.devDependencies = {};
        }
        if (!c.devDependencies["@0no-co/graphqlsp"]) {
          c.devDependencies["@0no-co/graphqlsp"] = "^1.8.0";
        }
      }
      await a.writeFile(E, JSON.stringify(c, null, 2));
      e.stop("Written to package.json.");
    } catch (D) {
      e.stop('Failed to write to package.json, you can try adding "gql.tada" and "@0no-co/graphqlsp" yourself.');
    }
  }
  e.start("Writing to tsconfig.json.");
  var h = "tsconfig.json";
  try {
    var m = s.resolve(D, "tsconfig.json");
    var g = await G(m);
    if (Array.isArray(g.references) && Array.isArray(g.files) && !g.files.length && !g.include) {
      var B;
      var b;
      for (var w of g.references) {
        if (!w || "string" != typeof w.path) {
          continue;
        }
        var S = s.resolve(D, w.path);
        if (".json" !== s.extname(S)) {
          S = s.join(S, "tsconfig.json");
        }
        try {
          await a.access(S);
        } catch (D) {
          continue;
        }
        if ("tsconfig.app.json" === s.basename(S)) {
          b = S;
          break;
        } else if (!B) {
          B = S;
        }
      }
      var I = b || B;
      if (I) {
        m = I;
        g = await G(m);
        h = s.relative(D, m);
      }
    }
    var M = r.endsWith(".json") || r.endsWith(".graphql");
    var _ = s.dirname(m);
    g.compilerOptions = {
      ...g.compilerOptions,
      plugins: [ {
        name: i ? "gql.tada/ts-plugin" : "@0no-co/graphqlsp",
        schema: M ? s.relative(_, s.resolve(D, r)) : r,
        tadaOutputLocation: s.relative(_, t)
      } ]
    };
    await a.writeFile(m, JSON.stringify(g, null, 2));
  } catch (D) {}
  e.stop(`Written to ${h}.`);
  ((D = "") => {
    process.stdout.write(`${Y.gray(Eu)}\n${Y.gray(fu)}  ${D}\n\n`);
  })("Off to the races!");
}

var question = async (D, e, r) => {
  var t = "";
  var n = !1;
  while (!n) {
    if (hD(t = await te({
      message: D
    }))) {
      n = !0;
      ue("Operation cancelled.");
      process.exit(0);
    } else if (await e(t)) {
      n = !0;
    }
  }
  return t;
};

export { run };
//# sourceMappingURL=runner-chunk.mjs.map
