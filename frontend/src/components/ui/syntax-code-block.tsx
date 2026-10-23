import { useTheme } from "@/components/theme-provider"
import { PrismLight as SyntaxHighlighter } from "react-syntax-highlighter"
import bash from "react-syntax-highlighter/dist/esm/languages/prism/bash"
import json from "react-syntax-highlighter/dist/esm/languages/prism/json"
import python from "react-syntax-highlighter/dist/esm/languages/prism/python"
import typescript from "react-syntax-highlighter/dist/esm/languages/prism/typescript"
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism"
import { cn } from "@/lib/utils"

SyntaxHighlighter.registerLanguage("python", python)
SyntaxHighlighter.registerLanguage("typescript", typescript)
SyntaxHighlighter.registerLanguage("bash", bash)
SyntaxHighlighter.registerLanguage("json", json)

export type SyntaxCodeLanguage = "python" | "typescript" | "curl" | "json"

const PRISM_LANG: Record<SyntaxCodeLanguage, string> = {
  python: "python",
  typescript: "typescript",
  curl: "bash",
  json: "json",
}

type SyntaxCodeBlockProps = {
  code: string
  language: SyntaxCodeLanguage
  className?: string
}

export function SyntaxCodeBlock({ code, language, className }: SyntaxCodeBlockProps) {
  const { mode } = useTheme()
  const prismStyle = mode === "dark" ? oneDark : oneLight

  return (
    <SyntaxHighlighter
      language={PRISM_LANG[language]}
      style={prismStyle}
      PreTag="div"
      showLineNumbers={false}
      wrapLongLines
      customStyle={{
        margin: 0,
        padding: 0,
        background: "transparent",
        minWidth: 0,
        maxWidth: "100%",
        overflowX: "hidden",
      }}
      codeTagProps={{
        className: cn(
          "syntax-code-block min-w-0 max-w-full break-words [overflow-wrap:anywhere] font-mono text-sm leading-relaxed",
          className,
        ),
      }}
    >
      {code.trimEnd()}
    </SyntaxHighlighter>
  )
}
