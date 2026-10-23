import { describe, expect, it } from "vitest"
import { cn } from "./utils"

describe("cn utility", () => {
  it("merges standard class names correctly", () => {
    const result = cn("class-a", "class-b")
    expect(result).toBe("class-a class-b")
  })

  it("handles conditional class names", () => {
    const isPrimary = true
    const isDisabled = false
    const result = cn("btn", isPrimary && "btn-primary", isDisabled && "btn-disabled")
    expect(result).toBe("btn btn-primary")
  })

  it("resolves conflicting Tailwind utility classes using tailwind-merge", () => {
    const paddingResult = cn("p-4", "p-2")
    expect(paddingResult).toBe("p-2")

    const colorResult = cn("text-red-500", "text-blue-500")
    expect(colorResult).toBe("text-blue-500")

    const bgResult = cn("bg-white", "bg-transparent")
    expect(bgResult).toBe("bg-transparent")
  })

  it("handles null, undefined, false, and empty string arguments safely", () => {
    const result = cn(null, undefined, false, "", "valid-class")
    expect(result).toBe("valid-class")
  })

  it("handles array of class names", () => {
    const result = cn(["flex", "items-center"], "justify-between")
    expect(result).toBe("flex items-center justify-between")
  })
})
