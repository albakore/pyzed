// /pyzed/llms.txt (https://llmstxt.org): the documentation map for AI assistants. See src/lib/llms.ts.
import { llmsTxt, textResponse } from '../lib/llms';

export const GET = async () => textResponse(await llmsTxt('en'));
