import { test, expect } from '@playwright/test';
import { SafetyDashboardPage } from './pages/SafetyDashboardPage';

test.describe('Industrial Safety Dashboard (E2E)', () => {
  let dashboard: SafetyDashboardPage;

  test.beforeEach(async ({ page }) => {
    dashboard = new SafetyDashboardPage(page);
    await dashboard.goto();
  });

  test('loads dashboard and displays brand and status metrics', async () => {
    await expect(dashboard.brandLink).toBeVisible();
    await expect(dashboard.nav).toBeVisible();
    await expect(dashboard.statsGrid).toBeVisible();

    // Verify key metrics cards are rendered
    await expect(dashboard.statsGrid.getByText(/Требуют реакции/i)).toBeVisible();
    await expect(dashboard.statsGrid.getByText(/Камеры онлайн/i)).toBeVisible();
    await expect(dashboard.statsGrid.getByText(/Устранено за смену/i)).toBeVisible();
  });

  test('navigates seamlessly across workspace views', async ({ page }) => {
    // 1. Navigate to Event Journal
    await dashboard.navigateTab('Журнал событий');
    await expect(page.locator('.journal-summary')).toBeVisible();

    // 2. Navigate to Cameras
    await dashboard.navigateTab('Камеры');
    await expect(page.locator('.camera-grid')).toBeVisible();

    // 3. Navigate to Analytics
    await dashboard.navigateTab('Аналитика');
    await expect(page.getByText('События в течение смены')).toBeVisible();

    // 4. Return to Overview
    await dashboard.navigateTab('Обзор');
    await expect(dashboard.statsGrid).toBeVisible();
  });

  test('switches industrial site and updates context', async ({ page }) => {
    // Select South Facility
    await dashboard.selectSite('south');
    await expect(dashboard.siteSelect).toHaveValue('south');
    await expect(page.locator('.facility-select strong')).toHaveText('Южная площадка');

    // Select North Facility
    await dashboard.selectSite('north');
    await expect(dashboard.siteSelect).toHaveValue('north');
    await expect(page.locator('.facility-select strong')).toHaveText('Завод «Северный»');
  });

  test('filters events by search query in event journal', async () => {
    await dashboard.navigateTab('Журнал событий');

    // Search for helmet incident
    await dashboard.searchEvents('каски');
    const tableRows = dashboard.eventsTable.locator('tbody tr');
    await expect(tableRows.first()).toContainText(/каск/i);

    // Clear search and verify rows are restored
    await dashboard.clearSearch();
    await expect(tableRows.first()).toBeVisible();
  });

  test('opens incident modal and transitions status to resolved', async () => {
    await dashboard.navigateTab('Журнал событий');
    await dashboard.openFirstEvent();

    // Verify modal elements
    await expect(dashboard.dialog).toBeVisible();
    await expect(dashboard.dialog.getByText(/Что произошло/i)).toBeVisible();
    await expect(dashboard.dialog.getByText(/Рекомендуемое действие/i)).toBeVisible();

    // Mark as resolved
    await dashboard.resolveSelectedEvent();

    // Status badge updates to resolved and action button is disabled
    await expect(dashboard.dialog.locator('.status-badge')).toHaveText(/Устранено/i);
    await expect(dashboard.dialog.getByRole('button', { name: /Нарушение устранено/i })).toBeDisabled();

    // Close modal
    await dashboard.closeDialog();
  });

  test('triggers CSV report export download', async ({ page }) => {
    const downloadPromise = page.waitForEvent('download');
    await dashboard.exportButton.click();
    const download = await downloadPromise;

    expect(download.suggestedFilename()).toContain('.csv');
  });
});
