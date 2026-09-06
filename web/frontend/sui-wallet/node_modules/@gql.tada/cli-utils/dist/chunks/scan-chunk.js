var t = require("node:path");

var e = require("typescript");

function _interopNamespaceDefault(t) {
  var e = Object.create(null);
  if (t) {
    Object.keys(t).forEach((function(r) {
      if ("default" !== r) {
        var n = Object.getOwnPropertyDescriptor(t, r);
        Object.defineProperty(e, r, n.get ? n : {
          enumerable: !0,
          get: function() {
            return t[r];
          }
        });
      }
    }));
  }
  e.default = t;
  return e;
}

var r = _interopNamespaceDefault(t);

var n = /(?:^|[^\w])(query|mutation|subscription|fragment)\b/;

exports.hasGraphQLDocumentCandidate = function hasGraphQLDocumentCandidate(t) {
  if (!t.text.includes("{")) {
    return !1;
  }
  var r = !1;
  var visit = t => {
    if (r) {
      return;
    }
    if (e.isCallExpression(t)) {
      var i = t.arguments[0];
      if (i && e.isStringLiteralLike(i)) {
        var a = i.text;
        if (a.includes("{") && function isGraphQLDocumentCandidateText(t) {
          if (n.test(t)) {
            return !0;
          }
          for (var e of t.split("\n")) {
            var r = e.trimStart();
            if (!r || r.startsWith("#")) {
              continue;
            }
            return r.startsWith("{");
          }
          return !1;
        }(a)) {
          r = !0;
          return;
        }
      }
    }
    e.forEachChild(t, visit);
  };
  visit(t);
  return r;
};

exports.shouldScanTurboFile = function shouldScanTurboFile(t, e) {
  if (e.has(r.resolve(t))) {
    return !1;
  }
  if (t.endsWith(".d.ts") || t.endsWith(".d.mts") || t.endsWith(".d.cts")) {
    return !1;
  }
  return !/(^|[/\\])node_modules([/\\]|$)/.test(t);
};
//# sourceMappingURL=scan-chunk.js.map
