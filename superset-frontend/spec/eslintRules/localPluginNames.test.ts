/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
import fs from 'fs';
import path from 'path';

/**
 * The ESLint plugins under `eslint-rules/` are Superset's own code, linked via
 * `file:` specifiers. An unscoped name for such a package collides with the
 * public npm namespace: `npm audit` matches advisories by name, and anything
 * resolving the name against the registry instead of the `file:` link pulls a
 * stranger's package. Scoped names are unsquattable, so keep them scoped.
 */
const SCOPE = '@superset-ui/';

const frontendRoot = path.resolve(__dirname, '../..');
const rulesRoot = path.join(frontendRoot, 'eslint-rules');

const readJson = (file: string) =>
  JSON.parse(fs.readFileSync(file, 'utf8')) as Record<string, unknown>;

const pluginDirs = fs
  .readdirSync(rulesRoot)
  .filter(entry => fs.existsSync(path.join(rulesRoot, entry, 'package.json')));

const rootPackageJson = readJson(path.join(frontendRoot, 'package.json'));
const devDependencies = rootPackageJson.devDependencies as Record<
  string,
  string
>;

test('local eslint plugins are published under a scoped name', () => {
  expect(pluginDirs.length).toBeGreaterThan(0);
  pluginDirs.forEach(dir => {
    const { name } = readJson(path.join(rulesRoot, dir, 'package.json'));
    expect(name).toBe(`${SCOPE}${dir}`);
  });
});

test('root package.json depends on the local plugins by their scoped name', () => {
  pluginDirs.forEach(dir => {
    expect(devDependencies[`${SCOPE}${dir}`]).toBe(`file:eslint-rules/${dir}`);
    expect(devDependencies[dir]).toBeUndefined();
  });
});

test('the eslint config loads the local plugins by their scoped name', () => {
  const config = fs.readFileSync(
    path.join(frontendRoot, 'eslint.config.minimal.js'),
    'utf8',
  );
  pluginDirs.forEach(dir => {
    expect(config).toContain(`require('${SCOPE}${dir}')`);
    expect(config).not.toContain(`require('${dir}')`);
  });
});

test('the lockfile has no unscoped entry for the local plugins', () => {
  const lockfile = fs.readFileSync(
    path.join(frontendRoot, 'package-lock.json'),
    'utf8',
  );
  pluginDirs.forEach(dir => {
    expect(lockfile).not.toContain(`"node_modules/${dir}"`);
    expect(lockfile).not.toContain(`"${dir}": "file:eslint-rules/${dir}"`);
  });
});
