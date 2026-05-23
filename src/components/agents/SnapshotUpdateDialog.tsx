import React from 'react'
import { Text } from '../../ink.js'
import type { AgentMemoryScope } from '../../tools/AgentTool/agentMemory.js'

export function buildMergePrompt(): string {
  return ''
}

export function SnapshotUpdateDialog(props: {
  agentType: string
  scope: AgentMemoryScope
  snapshotTimestamp: string
  onComplete: (choice: 'merge' | 'keep' | 'replace') => void
  onCancel: () => void
}) {
  React.useEffect(() => {
    props.onCancel()
  }, [props])

  return (
    <Text>
      Agent memory snapshot update is unavailable in the minimal build.
    </Text>
  )
}
