// SPDX-License-Identifier: GPL-3.0-or-later
import { test, expect } from '@playwright/test';

test('card models load on request, rotate, zoom, reset and switch', async ({ page }) => {
  const models = [];
  const external = [];
  const errors = [];
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.endsWith('.glb')) models.push(request.url());
    if (request.url().startsWith('http') && !request.url().startsWith('http://127.0.0.1:4173/')) external.push(request.url());
  });
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('./');
  await expect(page.getByRole('heading', { name: 'Slot-otter Forge' })).toBeVisible();
  await page.getByRole('button', { name: 'Classic DISCRETE' }).click();
  await expect(page.getByRole('heading', { name: 'Slot-otter Classic' })).toBeVisible();
  await expect(page.locator('#poster')).toHaveAttribute('src', /classic.webp$/);
  expect(models).toHaveLength(0);
  await page.getByRole('button', { name: 'Forge CPLD' }).click();
  await page.getByRole('button', { name: 'Explore in 3D' }).click();
  await expect(page.getByRole('button', { name: 'Reset view' })).toBeEnabled({ timeout: 60_000 });
  await expect.poll(() => page.locator('model-viewer').evaluate((element) => element.src)).toMatch(/forge\.glb\?v=[a-f0-9]{12}$/);
  expect(models).toHaveLength(1);
  const orbit = () => page.locator('model-viewer').evaluate((element) => {
    const { theta, phi, radius } = element.getCameraOrbit();
    return { theta, phi, radius };
  });
  const initial = await orbit();
  const box = await page.locator('model-viewer').boundingBox();
  await page.mouse.move(box.x + box.width * .5, box.y + box.height * .5);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width * .75, box.y + box.height * .6, { steps: 12 });
  await page.mouse.up();
  await expect.poll(async () => Math.abs((await orbit()).theta - initial.theta)).toBeGreaterThan(.2);
  const beforeZoom = await orbit();
  await page.mouse.wheel(0, -250);
  await expect.poll(async () => (await orbit()).radius).toBeLessThan(beforeZoom.radius * .95);
  await page.getByRole('button', { name: 'Reset view' }).click();
  await expect.poll(async () => Math.abs((await orbit()).theta - initial.theta)).toBeLessThan(.01);
  await expect.poll(async () => Math.abs((await orbit()).radius - initial.radius)).toBeLessThan(.001);
  await page.screenshot({ path: 'test-results/forge-desktop.png', fullPage: true });
  await page.getByRole('button', { name: 'Classic DISCRETE' }).click();
  await expect(page.getByRole('button', { name: 'Reset view' })).toBeEnabled({ timeout: 60_000 });
  await expect.poll(() => page.locator('model-viewer').evaluate((element) => element.src)).toMatch(/classic\.glb\?v=[a-f0-9]{12}$/);
  await expect(page.locator('#viewer-status')).toContainText('Classic ready');
  expect(models).toHaveLength(2);
  expect(external).toEqual([]);
  expect(errors).toEqual([]);
  await page.screenshot({ path: 'test-results/classic-desktop.png', fullPage: true });
});

test('mobile layout fits the viewport and retains card selection', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('./');
  await expect(page.getByRole('button', { name: 'Explore in 3D' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByRole('button', { name: 'Classic DISCRETE' }).click();
  await expect(page.getByRole('heading', { name: 'Slot-otter Classic' })).toBeVisible();
  await page.screenshot({ path: 'test-results/mobile.png', fullPage: true });
});

test('a failed model download offers retry without hiding the card photo', async ({ page }) => {
  await page.route('**/models/forge.glb*', (route) => route.abort());
  await page.goto('./');
  await page.getByRole('button', { name: 'Explore in 3D' }).click();
  await expect(page.locator('#viewer-status')).toContainText('could not load', { timeout: 60_000 });
  await expect(page.locator('#poster')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Explore in 3D' })).toBeEnabled();
  await page.unroute('**/models/forge.glb*');
  await page.getByRole('button', { name: 'Explore in 3D' }).click();
  await expect(page.getByRole('button', { name: 'Reset view' })).toBeEnabled({ timeout: 60_000 });
});
