import React from 'react'
import { Text } from '../ink.js'

export function AssistantSessionChooser(props: {
  sessions: Array<{ id?: string }>
  onSelect: (id: string) => void
  onCancel: () => void
}) {
  React.useEffect(() => {
    const firstSessionId = props.sessions[0]?.id
    if (firstSessionId) {
      props.onSelect(firstSessionId)
      return
    }
    props.onCancel()
  }, [props])

  return <Text>Assistant session picker is unavailable in the minimal build.</Text>
}
