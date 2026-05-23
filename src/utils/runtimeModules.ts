type RuntimeImport = <T = unknown>(specifier: string) => Promise<T>

const runtimeImport = Function(
  'specifier',
  'return import(specifier)',
) as RuntimeImport

export function isMissingRuntimeModuleError(
  error: unknown,
  specifier?: string,
): boolean {
  const code = (error as { code?: string } | null | undefined)?.code
  if (code === 'ERR_MODULE_NOT_FOUND' || code === 'MODULE_NOT_FOUND') {
    return true
  }

  if (!(error instanceof Error)) {
    return false
  }

  return (
    error.message.includes('Cannot find module') ||
    error.message.includes('Could not resolve') ||
    (specifier ? error.message.includes(specifier) : false)
  )
}

export function importRuntimeModule<T = unknown>(
  specifier: string,
): Promise<T> {
  return runtimeImport<T>(specifier)
}

export async function importOptionalRuntimeModule<T = unknown>(
  specifier: string,
): Promise<T | null> {
  try {
    return await importRuntimeModule<T>(specifier)
  } catch (error) {
    if (isMissingRuntimeModuleError(error, specifier)) {
      return null
    }
    throw error
  }
}

export async function importRequiredRuntimeModule<T = unknown>(
  specifier: string,
  context: string,
): Promise<T> {
  const mod = await importOptionalRuntimeModule<T>(specifier)
  if (mod !== null) {
    return mod
  }

  throw new Error(
    `${context} requires optional module "${specifier}", which is not available in this minimal build.`,
  )
}
