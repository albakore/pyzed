// /pyzed/llms-full.txt: the whole English documentation as one Markdown file. See src/lib/llms.ts.
import { llmsFull, textResponse } from '../lib/llms';

export const GET = async () => textResponse(await llmsFull('en'));
