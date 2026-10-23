import { type Page, type Locator, expect } from '@playwright/test';

/**
 * Page Object Model for the LinQ Industrial Safety Dashboard.
 * Adheres to playwright-expert guidelines: role-based selectors, encapsulation, auto-waiting.
 */
export class SafetyDashboardPage {
  readonly page: Page;
  readonly brandLink: Locator;
  readonly nav: Locator;
  readonly siteSelect: Locator;
  readonly exportButton: Locator;
  readonly searchInput: Locator;
  readonly statsGrid: Locator;
  readonly dialog: Locator;
  readonly eventsTable: Locator;

  constructor(page: Page) {
    this.page = page;
    this.brandLink = page.getByRole('link', { name: /Тук-Тук/i });
    this.nav = page.getByRole('navigation', { name: 'Основная навигация' });
    this.siteSelect = page.getByRole('combobox', { name: 'Выбор площадки' });
    this.exportButton = page.getByRole('button', { name: /Экспорт/i });
    this.searchInput = page.getByRole('textbox', { name: 'Поиск' });
    this.statsGrid = page.locator('.stats-grid');
    this.dialog = page.locator('.event-dialog');
    this.eventsTable = page.locator('.event-table');
  }

  async goto() {
    await this.page.goto('/');
    await expect(this.brandLink).toBeVisible();
  }

  async navigateTab(name: string) {
    const tabButton = this.nav.getByRole('button', { name: new RegExp(name, 'i') });
    await tabButton.click();
  }

  async selectSite(siteId: string) {
    await this.siteSelect.selectOption(siteId);
  }

  async searchEvents(query: string) {
    await this.searchInput.fill(query);
  }

  async clearSearch() {
    const clearBtn = this.page.getByRole('button', { name: 'Очистить поиск' });
    if (await clearBtn.isVisible()) {
      await clearBtn.click();
    }
  }

  async openFirstEvent() {
    const firstEventBtn = this.eventsTable.locator('.event-table-name').first();
    await firstEventBtn.click();
    await expect(this.dialog).toBeVisible();
  }

  async resolveSelectedEvent() {
    const resolveBtn = this.dialog.getByRole('button', { name: /Нарушение устранено/i });
    await resolveBtn.click();
  }

  async takeSelectedEventToWork() {
    const workBtn = this.dialog.getByRole('button', { name: /Взять в работу/i });
    await workBtn.click();
  }

  async markAsFalsePositive() {
    const dismissBtn = this.dialog.getByRole('button', { name: /Ложное срабатывание/i });
    await dismissBtn.click();
  }

  async closeDialog() {
    await this.page.keyboard.press('Escape');
    await expect(this.dialog).not.toBeVisible();
  }
}
