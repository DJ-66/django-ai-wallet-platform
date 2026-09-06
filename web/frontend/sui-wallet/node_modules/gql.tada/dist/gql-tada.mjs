import { Kind as r, parse as a } from "@0no-co/graphql.web";

export { maskFragments, unsafe_readResult } from "./gql-tada-testing.mjs";

var n = 0;

var e = new Set;

function initGraphQLTada() {
  function graphql(t, i) {
    var o = a(t).definitions;
    var s = new Set;
    for (var d of i || []) {
      for (var f of d.definitions) {
        if (f.kind === r.FRAGMENT_DEFINITION && !s.has(f)) {
          o.push(f);
          s.add(f);
        }
      }
    }
    var c;
    if ((c = o[0].kind === r.FRAGMENT_DEFINITION) && o[0].directives) {
      o[0].directives = o[0].directives.filter((r => "_unmask" !== r.name.value));
    }
    var u;
    return {
      kind: r.DOCUMENT,
      definitions: o,
      get loc() {
        if (!u && c) {
          var r = t + function concatLocSources(r) {
            try {
              n++;
              var a = "";
              for (var t of r) {
                if (!e.has(t)) {
                  e.add(t);
                  var {loc: i} = t;
                  if (i) {
                    a += i.source.body;
                  }
                }
              }
              return a;
            } finally {
              if (0 == --n) {
                e.clear();
              }
            }
          }(i || []);
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
        return u;
      },
      set loc(r) {
        u = r;
      }
    };
  }
  graphql.scalar = function scalar(r, a) {
    return a;
  };
  graphql.persisted = function persisted(a, n) {
    return {
      kind: r.DOCUMENT,
      definitions: n ? n.definitions : [],
      documentId: a
    };
  };
  return graphql;
}

function parse(r) {
  return a(r);
}

function readFragment(...r) {
  return 2 === r.length ? r[1] : r[0];
}

var t = initGraphQLTada();

export { t as graphql, initGraphQLTada, parse, readFragment };
//# sourceMappingURL=gql-tada.mjs.map
