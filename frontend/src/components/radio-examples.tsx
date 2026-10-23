import { useState } from "react"
import { Button } from "@/components/ui/button"
import { RadioControl, RadioField, RadioHrField, RadioGroup } from "@/components/ui/radio-group"

const options = [
  { label: "Unchecked", value: "off" },
  { label: "Checked", value: "on" },
] as const

export default function RadioExamples() {
  const [resetKey, setResetKey] = useState(0)
  return (
    <div id="radio-buttons" className="scroll-mt-24">
      <div key={resetKey} className="grid gap-8 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <div>
          <p className="mb-5 text-sm font-medium">HR Control · no label</p>
          <div className="grid w-fit grid-cols-[auto_24px_24px] items-center gap-x-5 gap-y-5">
            <span />
            <span className="justify-self-center text-[10px] text-muted-foreground">Enabled</span>
            <span className="justify-self-center text-[10px] text-muted-foreground">Disabled</span>
            <span className="col-start-1 row-start-2 text-xs text-muted-foreground">Unchecked</span>
            <span className="col-start-1 row-start-3 text-xs text-muted-foreground">Checked</span>
            {(["Enabled", "Disabled"] as const).map((state, index) => (
              <RadioGroup
                key={state}
                defaultValue="on"
                aria-label={`${state} HR radio examples`}
                className={`row-span-2 row-start-2 gap-5 ${index === 0 ? "col-start-2" : "col-start-3"}`}
              >
                {options.map(({ label, value }) => (
                  <RadioControl
                    key={value}
                    value={value}
                    state={state}
                    aria-label={`${state} ${label.toLowerCase()} HR radio`}
                  />
                ))}
              </RadioGroup>
            ))}
            <span className="col-start-1 row-start-4 text-xs text-muted-foreground">Shimmer</span>
            <RadioGroup
              value="loading"
              aria-label="Loading HR radio example"
              className="col-start-2 row-start-4"
            >
              <RadioControl value="loading" state="Shimmer" aria-label="Loading HR radio" />
            </RadioGroup>
          </div>
        </div>
        <div>
          <p className="mb-5 text-sm font-medium">HR Field · optional text</p>
          <div className="grid grid-cols-[auto_repeat(3,minmax(0,1fr))] items-center gap-x-3 gap-y-5">
            <span />
            {(["Default", "Focus", "Disabled"] as const).map((state) => (
              <span key={state} className="text-center text-[10px] text-muted-foreground">
                {state}
              </span>
            ))}
            <div className="row-span-2 grid gap-5 self-start text-xs text-muted-foreground">
              <span className="flex h-6 items-center">Unchecked</span>
              <span className="flex h-6 items-center">Checked</span>
            </div>
            {(["Default", "Focus", "Disabled"] as const).map((state) => (
              <RadioGroup
                key={state}
                defaultValue="on"
                aria-label={`${state} HR field examples`}
                className="row-span-2 gap-5"
              >
                {options.map(({ label, value }) => (
                  <RadioHrField
                    key={value}
                    value={value}
                    state={state}
                    label={`${state} ${label.toLowerCase()} HR radio field`}
                    className="justify-center"
                  />
                ))}
              </RadioGroup>
            ))}
          </div>
          <div className="mt-8 space-y-4">
            <p className="text-xs text-muted-foreground">Show text · one choice per group</p>
            <RadioGroup
              defaultValue="first"
              aria-label="Choose an example option"
              className="gap-4"
            >
              <RadioHrField
                showText
                value="first"
                label="Choose option"
                description="Optional supporting text"
              />
              <RadioHrField showText value="second" label="Another option" />
            </RadioGroup>
          </div>
        </div>
      </div>
      <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <p className="text-xs text-muted-foreground">
          24 × 24px control · 22px ring · 12px dot · 2px stroke
        </p>
        <Button variant="ghost" size="sm" onClick={() => setResetKey((key) => key + 1)}>
          Reset radio examples
        </Button>
      </div>
      <details className="mt-4 border-t border-border pt-4">
        <summary className="cursor-pointer text-xs text-muted-foreground">
          Base radio · shadcn/ui · 16px
        </summary>
        <RadioGroup defaultValue="standard" className="mt-4 gap-4">
          <RadioField
            value="standard"
            label="Standard option"
            description="Supporting text shows the field description style."
          />
          <RadioField value="alternative" label="Alternative option" controlPlacement="End" />
          <RadioField value="boxed" label="Box variant" type="Box" />
        </RadioGroup>
      </details>
    </div>
  )
}
