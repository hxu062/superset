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

// Regression guard for GHSA-395f-4hp3-45gv: shell-quote <=1.8.4 has a
// quadratic-complexity ReDoS in parse(). It reaches the dev/CI toolchain
// through concurrently. Assert every resolved copy in the lockfile is past
// the vulnerable range so a lockfile refresh cannot silently reintroduce it.
type LockPackages = Record<string, { version?: string }>;

function compareSemver(a: string, b: string): number {
  const pa = a.split('.').map(Number);
  const pb = b.split('.').map(Number);
  for (let i = 0; i < 3; i += 1) {
    const diff = (pa[i] ?? 0) - (pb[i] ?? 0);
    if (diff !== 0) return diff > 0 ? 1 : -1;
  }
  return 0;
}

function resolvedVersions(packages: LockPackages, name: string): string[] {
  const suffix = `node_modules/${name}`;
  return Object.entries(packages)
    .filter(([key]) => key === suffix || key.endsWith(`/${suffix}`))
    .map(([, value]) => value.version)
    .filter((version): version is string => Boolean(version));
}

test('shell-quote resolves past the GHSA-395f-4hp3-45gv vulnerable range', () => {
  const lockPath = path.resolve(__dirname, '../../package-lock.json');
  const { packages } = JSON.parse(fs.readFileSync(lockPath, 'utf8')) as {
    packages: LockPackages;
  };

  const versions = resolvedVersions(packages, 'shell-quote');
  expect(versions.length).toBeGreaterThan(0);
  versions.forEach(version => {
    // Vulnerable range is <=1.8.4; the fix ships in 1.9.0.
    expect(compareSemver(version, '1.8.4')).toBeGreaterThan(0);
  });
});
