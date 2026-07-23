// Dispara a animação de "boot" pós-login (consumida por <BootSequence/>).
export const BOOT_EVENT = 'ad-boot'

export function triggerBoot(): void {
  window.dispatchEvent(new CustomEvent(BOOT_EVENT))
}
