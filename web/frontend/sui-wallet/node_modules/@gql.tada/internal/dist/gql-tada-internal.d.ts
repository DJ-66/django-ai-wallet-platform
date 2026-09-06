import { IntrospectionQuery, GraphQLSchema } from 'graphql';
import ts from 'typescript';
import { TsConfigJson } from 'type-fest';

interface IntrospectionResult extends IntrospectionQuery {
  name: string | undefined;
}
interface SchemaLoaderResult {
  introspection: IntrospectionResult;
  schema: GraphQLSchema;
  tadaOutputLocation?: string;
  tadaTurboLocation?: string;
  tadaPersistedLocation?: string;
}
type OnSchemaUpdate = (result: SchemaLoaderResult) => void;
type OnSchemaError = (error: Error) => void;
interface SchemaLoader {
  readonly name: string | undefined;
  load(reload?: boolean): Promise<SchemaLoaderResult>;
  notifyOnUpdate(onUpdate: OnSchemaUpdate, onError?: OnSchemaError): () => void;
  /** @internal */
  loadIntrospection(): Promise<IntrospectionResult | null>;
  /** @internal */
  loadSchema(): Promise<GraphQLSchema | null>;
}
interface BaseLoadConfig {
  rootPath?: string;
  fetchInterval?: number;
  assumeValid?: boolean;
}
type SingleSchemaInput = {
  name?: string;
  schema: SchemaOrigin;
  tadaOutputLocation?: string;
  tadaTurboLocation?: string;
  tadaPersistedLocation?: string;
};
type MultiSchemaInput = {
  schemas?: SingleSchemaInput[];
};
interface SchemaRef<Result = SchemaLoaderResult | null> {
  /** Starts automatically updating the ref */
  autoupdate(
    config: BaseLoadConfig,
    onUpdate: (ref: SchemaRef<Result>, input: SingleSchemaInput) => void,
    onError?: (error: Error, input: SingleSchemaInput) => void
  ): () => void;
  /** Loads the initial result for the schema.
   * Loaders cache their last successful result; pass `reload` to force
   * re-reading schemas, e.g. when a file watcher may have missed events. */
  load(
    config: BaseLoadConfig & {
      reload?: boolean;
    }
  ): Promise<SchemaRef<SchemaLoaderResult>>;
  current: Result;
  multi: {
    [name: string]: Result;
  };
  version: number;
}
type SchemaOrigin =
  | string
  | {
      url: string;
      headers?: HeadersInit;
    };

interface LoadFromSDLConfig {
  name?: string;
  assumeValid?: boolean;
  file: string;
}
declare function loadFromSDL(config: LoadFromSDLConfig): SchemaLoader;

interface LoadFromURLConfig {
  name?: string;
  url: URL | string;
  headers?: HeadersInit;
  interval?: number;
}
declare function loadFromURL(config: LoadFromURLConfig): SchemaLoader;

declare const getURLConfig: (origin: SchemaOrigin | null) => {
  url: URL;
  headers: HeadersInit | undefined;
} | null;
interface LoadConfig extends BaseLoadConfig {
  name?: string;
  origin: SchemaOrigin;
}
declare function load(config: LoadConfig): SchemaLoader;
declare function loadRef(
  input: SingleSchemaInput | MultiSchemaInput | (SingleSchemaInput & MultiSchemaInput)
): SchemaRef;

declare class TSError extends Error {
  readonly name: 'TSError';
  readonly diagnostic: ts.Diagnostic;
  constructor(diagnostic: ts.Diagnostic);
}
declare class TadaError extends Error {
  readonly name: 'TadaError';
  constructor(message: string);
}

interface BaseConfig {
  template?: string;
  trackFieldUsage?: boolean;
  shouldCheckForColocatedFragments?: boolean;
}
interface SchemaConfig {
  name?: string;
  schema: SchemaOrigin;
  tadaOutputLocation?: string;
  tadaTurboLocation?: string;
  tadaPersistedLocation?: string;
}
interface MultiSchemaConfig extends SchemaConfig {
  name: string;
}
type GraphQLSPConfig = BaseConfig &
  (
    | SchemaConfig
    | {
        schemas: MultiSchemaConfig[];
      }
  );
declare const parseConfig: (
  input: unknown,
  /** Defines the path of the "main" `tsconfig.json` file.
   * @remarks
   * This should be the `rootPath` output from `loadConfig`,
   * which is the path of the user's `tsconfig.json` before
   * resolving `extends` options.
   */
  rootPath?: string
) => GraphQLSPConfig;
interface ProjectConfig {
  /** Directory that relative output locations resolve against. */
  projectPath: string;
  config: GraphQLSPConfig;
  /** Display name for error messages, e.g. a relative tsconfig path. */
  label?: string;
}
declare const validateUniqueOutputLocations: (projects: readonly ProjectConfig[]) => void;
declare const getSchemaNamesFromConfig: (config: GraphQLSPConfig) => Set<null | string>;
declare const getSchemaConfigForName: (
  config: GraphQLSPConfig,
  name: string | undefined
) => SchemaConfig | null;

declare const readTSConfigFile: (filePath: string) => Promise<TsConfigJson>;
declare const findTSConfigFile: (targetPath?: string) => Promise<string | null>;
interface LoadConfigResult {
  pluginConfig: Record<string, unknown>;
  /** The config file in which the plugin entry was found (may be an `extends` base file). */
  configPath: string;
  /** The project's own tsconfig.json file, before `extends` resolution. */
  tsconfigPath: string;
  rootPath: string;
}
declare const loadConfigs: (targetPath?: string) => Promise<LoadConfigResult[]>;
declare const loadConfig: (targetPath?: string) => Promise<LoadConfigResult>;
/** @deprecated Use {@link loadConfig} instead */
declare const resolveTypeScriptRootDir: (tsconfigPath: string) => Promise<string | undefined>;

/** Minifies an {@link IntrospectionQuery} for use with Graphcache or the `populateExchange`.
 *
 * @param schema - An {@link IntrospectionQuery} object to be minified.
 * @param opts - An optional {@link MinifySchemaOptions} configuration object.
 * @returns the minified {@link IntrospectionQuery} object.
 *
 * @remarks
 * `minifyIntrospectionQuery` reduces the size of an {@link IntrospectionQuery} by
 * removing data and information that a client-side consumer, like Graphcache or the
 * `populateExchange`, may not require.
 *
 * At the very least, it will remove system types, descriptions, depreactions,
 * and source locations. Unless disabled via the options passed, it will also
 * by default remove all scalars, enums, inputs, and directives.
 *
 * @throws
 * If `schema` receives an object that isn’t an {@link IntrospectionQuery}, a
 * {@link TypeError} will be thrown.
 */
declare const minifyIntrospectionQuery: (
  schema: IntrospectionQuery | IntrospectionResult
) => IntrospectionResult;

declare function preprocessIntrospection(
  introspection: IntrospectionResult | IntrospectionQuery,
  typesStr?: string
): string;

/** Extracts the leading comment header of a previously generated file, so it
 * can be preserved across regenerations. Returns `null` when no custom header
 * is present (or when only the generated annotation remains). */
declare function extractIntrospectionHeader(contents: string): string | null;
interface OutputIntrospectionFileOptions {
  fileType: '.ts' | '.d.ts' | string;
  shouldPreprocess?: boolean;
  /** A custom leading comment header used in place of the default preamble,
   * typically extracted from a prior file via `extractIntrospectionHeader`. */
  preamble?: string;
}
declare function outputIntrospectionFile(
  introspection: IntrospectionQuery | IntrospectionResult,
  opts: OutputIntrospectionFileOptions
): string;

export {
  type BaseConfig,
  type BaseLoadConfig,
  type GraphQLSPConfig,
  type IntrospectionResult,
  type LoadConfig,
  type LoadConfigResult,
  type MultiSchemaInput,
  type OnSchemaError,
  type OnSchemaUpdate,
  type ProjectConfig,
  type SchemaConfig,
  type SchemaLoader,
  type SchemaLoaderResult,
  type SchemaOrigin,
  type SchemaRef,
  type SingleSchemaInput,
  TSError,
  TadaError,
  extractIntrospectionHeader,
  findTSConfigFile,
  getSchemaConfigForName,
  getSchemaNamesFromConfig,
  getURLConfig,
  load,
  loadConfig,
  loadConfigs,
  loadFromSDL,
  loadFromURL,
  loadRef,
  minifyIntrospectionQuery as minifyIntrospection,
  outputIntrospectionFile,
  parseConfig,
  preprocessIntrospection,
  readTSConfigFile,
  resolveTypeScriptRootDir,
  validateUniqueOutputLocations,
};
