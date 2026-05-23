import React from 'react'
import { homedir } from 'os'
import { join } from 'path'
import { Text } from '../../ink.js'

export async function computeDefaultInstallDir(): Promise<string> {
  return join(homedir(), '.claude', 'assistant')
}

export function NewInstallWizard(props: {
  defaultDir: string
  onInstalled: (dir: string) => void
  onCancel: () => void
  onError: (message: string) => void
}) {
  React.useEffect(() => {
    props.onCancel()
  }, [props])

  return <Text>Assistant install wizard is unavailable in the minimal build.</Text>
}
