import { NextRequest, NextResponse } from 'next/server';

const AI_ENGINE_URL = 'http://ai-engine:8000';

async function proxy(req: NextRequest, { params }: { params: { path: string[] } }) {
  const path = params.path.join('/');
  const searchParams = req.nextUrl.searchParams.toString();
  const url = `${AI_ENGINE_URL}/${path}${searchParams ? `?${searchParams}` : ''}`;
  
  console.log(`[Proxy] ${req.method} ${url}`);

  try {
    const headers = new Headers();
    // Forward relevant headers
    const contentType = req.headers.get('Content-Type');
    if (contentType) headers.set('Content-Type', contentType);
    
    // Only forward body for methods that support it
    const body = ['GET', 'HEAD'].includes(req.method) 
      ? undefined 
      : await req.text();

    const response = await fetch(url, {
      method: req.method,
      headers,
      body,
      cache: 'no-store',
    });

    // Handle SSE Streaming
    if (path.includes('stream/logs') || path.includes('stream/monitor')) {
      console.log("[Proxy] Streaming SSE response...");
      return new NextResponse(response.body, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      });
    }

    // Handle standard JSON/Text responses
    const responseContentType = response.headers.get('Content-Type');
    
    if (responseContentType?.includes('application/json')) {
      const data = await response.json();
      return NextResponse.json(data, { status: response.status });
    } 
    
    const text = await response.text();
    return new NextResponse(text, { 
      status: response.status,
      headers: {
        'Content-Type': responseContentType || 'text/plain'
      }
    });

  } catch (error) {
    console.error('[Proxy] Error:', error);
    return NextResponse.json(
      { error: 'Internal Proxy Error', details: String(error) }, 
      { status: 500 }
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
