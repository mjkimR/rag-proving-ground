import { createClient } from '@hey-api/openapi-ts';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const projectRoot = path.resolve(__dirname, '..');

const inputUrl = process.env.VITE_API_BASE_URL
    ? `${process.env.VITE_API_BASE_URL}/openapi.json`
    : 'http://localhost:8389/openapi.json';

const outputDir = path.resolve(projectRoot, 'src/generated/api');
// Use a temp file name that is unlikely to collide
const tempFile = path.resolve(projectRoot, 'temp_openapi.json');

const localFile = path.resolve(projectRoot, 'openapi.json');

if (fs.existsSync(localFile)) {
    console.log(`Found local OpenAPI definition at ${localFile}. Using it directly.`);
    fs.copyFileSync(localFile, tempFile);
} else {
    console.log(`No local openapi.json found. Fetching from ${inputUrl}...`);
    try {
        const response = await fetch(inputUrl);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();

        // Save to temp file
        fs.writeFileSync(tempFile, JSON.stringify(data, null, 2));
        console.log(`Saved API definition to ${tempFile}`);
    } catch (error) {
        console.error('Error fetching API definition:', error);
        process.exit(1);
    }
}

console.log(`Generating API client to ${outputDir}...`);

// Clean output directory
if (fs.existsSync(outputDir)) {
    console.log('Cleaning output directory...');
    fs.rmSync(outputDir, { recursive: true, force: true });
}

// Generate API
try {
    await createClient({
        input: tempFile,
        output: outputDir,
        plugins: [
            '@hey-api/client-fetch',
            '@hey-api/typescript',
            '@hey-api/sdk'
        ]
    });
    console.log('API generated successfully!');
} catch (error) {
    console.error('Error generating API:', error);
} finally {
    // Clean up temp file
    if (fs.existsSync(tempFile)) {
        console.log(`Removing temp file ${tempFile}...`);
        fs.rmSync(tempFile, { force: true });
    }
}
