import { useState } from "react"
import { Checkbox } from "@/components/ui/checkbox"
import { CheckboxControl, CheckboxField } from "@/components/ui/checkbox-control"
import { Button } from "@/components/ui/button"

const values = [
  { label: "Unchecked", checked: false },
  { label: "Checked", checked: true },
  { label: "Mixed", checked: "indeterminate" },
] as const

export default function CheckboxExamples() {
  const [resetKey, setResetKey] = useState(0)
  return (
    <div id="checkboxes" className="scroll-mt-24">
      <div key={resetKey} className="grid gap-8 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <div>
          <p className="mb-5 text-sm font-medium">HR Control · no label</p>
          <div className="grid w-fit grid-cols-[auto_24px_24px] items-center gap-x-5 gap-y-5">
            <span />
            <span className="justify-self-center text-[10px] text-muted-foreground">Enabled</span>
            <span className="justify-self-center text-[10px] text-muted-foreground">Disabled</span>
            {values.map(({ label, checked }) => (
              <div key={label} className="contents">
                <span className="text-xs text-muted-foreground">{label}</span>
                <CheckboxControl defaultChecked={checked} aria-label={`${label} HR checkbox`} />
                <CheckboxControl
                  defaultChecked={checked}
                  state="Disabled"
                  aria-label={`Disabled ${label.toLowerCase()} HR checkbox`}
                />
              </div>
            ))}
            <span className="text-xs text-muted-foreground">Shimmer</span>
            <CheckboxControl
              state="Shimmer"
              checked="indeterminate"
              aria-label="Loading HR checkbox"
            />
            <span />
          </div>
        </div>
        <div>
          <p className="mb-5 text-sm font-medium">HR Field · optional text</p>
          <div className="grid grid-cols-[auto_repeat(3,minmax(0,1fr))] items-center gap-x-3 gap-y-5">
            <span />
            {["Default", "Focus", "Disabled"].map((state) => (
              <span key={state} className="text-center text-[10px] text-muted-foreground">
                {state}
              </span>
            ))}
            {values.map(({ label, checked }) => (
              <div key={label} className="contents">
                <span className="text-xs text-muted-foreground">{label}</span>
                {(["Default", "Focus", "Disabled"] as const).map((state) => (
                  <CheckboxField
                    key={state}
                    state={state}
                    defaultChecked={checked}
                    label={`${state} ${label.toLowerCase()} HR field`}
                    className="justify-center"
                  />
                ))}
              </div>
            ))}
          </div>
          <div className="mt-8 space-y-4">
            <p className="text-xs text-muted-foreground">Show text</p>
            <CheckboxField
              showText
              defaultChecked
              label="Accept terms"
              description="Optional supporting text"
            />
          </div>
        </div>
      </div>
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <p className="text-xs text-muted-foreground">
          24 × 24px control · 20 × 20px fill · 2px stroke · 4px radius
        </p>
        <Button variant="ghost" size="sm" onClick={() => setResetKey((key) => key + 1)}>
          Reset checkbox examples
        </Button>
      </div>
      <details className="mt-4 border-t border-border pt-4">
        <summary className="cursor-pointer text-xs text-muted-foreground">
          Base checkbox · shadcn/ui · 16px
        </summary>
        <div className="mt-4 flex flex-wrap gap-4">
          <label className="flex items-center gap-2 text-sm">
            <Checkbox defaultChecked />
            Checked
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox />
            Unchecked
          </label>
        </div>
      </details>
    </div>
  )
}
