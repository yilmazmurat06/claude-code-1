import { getCachedMCConfig as getCachedMCConfigBase } from './cachedMCConfig.js'

export type CacheEditsBlock = {
  type: 'cache_edits'
  cache_control?: {
    type: string
  }
  edits: Array<{
    type: 'delete'
    tool_use_id: string
  }>
}

export type PinnedCacheEdits = {
  userMessageIndex: number
  block: CacheEditsBlock
}

export type CachedMCState = {
  deletedRefs: Set<string>
  pinnedEdits: PinnedCacheEdits[]
  registeredTools: Set<string>
  toolGroups: string[][]
  toolOrder: string[]
}

type CachedMCConfig = {
  enabled: boolean
  keepRecent: number
  supportedModels: string[]
  triggerThreshold: number
}

export function createCachedMCState(): CachedMCState {
  return {
    deletedRefs: new Set(),
    pinnedEdits: [],
    registeredTools: new Set(),
    toolGroups: [],
    toolOrder: [],
  }
}

export function getCachedMCConfig(): CachedMCConfig {
  return (
    getCachedMCConfigBase() ?? {
      enabled: false,
      keepRecent: 0,
      supportedModels: [],
      triggerThreshold: Number.POSITIVE_INFINITY,
    }
  )
}

export function isCachedMicrocompactEnabled(): boolean {
  return false
}

export function isModelSupportedForCacheEditing(): boolean {
  return false
}

export function registerToolResult(
  state: CachedMCState,
  toolUseId: string,
): void {
  state.registeredTools.add(toolUseId)
  state.toolOrder.push(toolUseId)
}

export function registerToolMessage(
  state: CachedMCState,
  groupIds: string[],
): void {
  if (groupIds.length > 0) {
    state.toolGroups.push(groupIds)
  }
}

export function getToolResultsToDelete(): string[] {
  return []
}

export function createCacheEditsBlock(): CacheEditsBlock | null {
  return null
}

export function markToolsSentToAPI(): void {}

export function resetCachedMCState(state: CachedMCState): void {
  state.deletedRefs.clear()
  state.pinnedEdits.length = 0
  state.registeredTools.clear()
  state.toolGroups.length = 0
  state.toolOrder.length = 0
}
