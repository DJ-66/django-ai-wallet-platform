Object.defineProperty(exports, "__esModule", {
  value: !0
});

var r = require("@0no-co/graphql.web");

var e = require("./gql-tada-testing.js");

var a = 0;

var n = new Set;

function initGraphQLTada() {
  function graphql(e, t) {
    var i = r.parse(e).definitions;
    var s = new Set;
    for (var o of t || []) {
      for (var d of o.definitions) {
        if (d.kind === r.Kind.FRAGMENT_DEFINITION && !s.has(d)) {
          i.push(d);
          s.add(d);
        }
      }
    }
    var u;
    if ((u = i[0].kind === r.Kind.FRAGMENT_DEFINITION) && i[0].directives) {
      i[0].directives = i[0].directives.filter((r => "_unmask" !== r.name.value));
    }
    var f;
    return {
      kind: r.Kind.DOCUMENT,
      definitions: i,
      get loc() {
        if (!f && u) {
          var r = e + function concatLocSources(r) {
            try {
              a++;
              var e = "";
              for (var t of r) {
                if (!n.has(t)) {
                  n.add(t);
                  var {loc: i} = t;
                  if (i) {
                    e += i.source.body;
                  }
                }
              }
              return e;
            } finally {
              if (0 == --a) {
                n.clear();
              }
            }
          }(t || []);
          return {
            start: 0,
            end: r.length,
            source: {
              body: r,
              name: "GraphQLTada",
              locationOffset: {
                line: 1,
                column: 1
              }
            }
          };
        }
        return f;
      },
      set loc(r) {
        f = r;
      }
    };
  }
  graphql.scalar = function scalar(r, e) {
    return e;
  };
  graphql.persisted = function persisted(e, a) {
    return {
      kind: r.Kind.DOCUMENT,
      definitions: a ? a.definitions : [],
      documentId: e
    };
  };
  return graphql;
}

var t = initGraphQLTada();

exports.maskFragments = e.maskFragments;

exports.unsafe_readResult = e.unsafe_readResult;

exports.graphql = t;

exports.initGraphQLTada = initGraphQLTada;

exports.parse = function parse(e) {
  return r.parse(e);
};

exports.readFragment = function readFragment(...r) {
  return 2 === r.length ? r[1] : r[0];
};
//# sourceMappingURL=gql-tada.js.map
