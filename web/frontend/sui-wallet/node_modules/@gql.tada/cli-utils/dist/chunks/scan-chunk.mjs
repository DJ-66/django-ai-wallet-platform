import * as t from "node:path";

import r from "typescript";

function shouldScanTurboFile(r, e) {
  if (e.has(t.resolve(r))) {
    return !1;
  }
  if (r.endsWith(".d.ts") || r.endsWith(".d.mts") || r.endsWith(".d.cts")) {
    return !1;
  }
  return !/(^|[/\\])node_modules([/\\]|$)/.test(r);
}

var e = /(?:^|[^\w])(query|mutation|subscription|fragment)\b/;

function hasGraphQLDocumentCandidate(t) {
  if (!t.text.includes("{")) {
    return !1;
  }
  var i = !1;
  var visit = t => {
    if (i) {
      return;
    }
    if (r.isCallExpression(t)) {
      var n = t.arguments[0];
      if (n && r.isStringLiteralLike(n)) {
        var s = n.text;
        if (s.includes("{") && function isGraphQLDocumentCandidateText(t) {
          if (e.test(t)) {
            return !0;
          }
          for (var r of t.split("\n")) {
            var i = r.trimStart();
            if (!i || i.startsWith("#")) {
              continue;
            }
            return i.startsWith("{");
          }
          return !1;
        }(s)) {
          i = !0;
          return;
        }
      }
    }
    r.forEachChild(t, visit);
  };
  visit(t);
  return i;
}

export { hasGraphQLDocumentCandidate as h, shouldScanTurboFile as s };
//# sourceMappingURL=scan-chunk.mjs.map
