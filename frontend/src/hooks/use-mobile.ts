import { useSyncExternalStore } from "react"

export const MOBILE_MEDIA_QUERY = "(max-width: 767px)"

function subscribe(callback: () => void) {
  const query = window.matchMedia(MOBILE_MEDIA_QUERY)
  query.addEventListener("change", callback)
  return () => query.removeEventListener("change", callback)
}

function getSnapshot() {
  return window.matchMedia(MOBILE_MEDIA_QUERY).matches
}

function getServerSnapshot() {
  return false
}

export function useIsMobile() {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot)
}

export function isMobileViewport() {
  return typeof window !== "undefined" && window.matchMedia(MOBILE_MEDIA_QUERY).matches
}
