"use client";

import { createChart, ColorType, IChartApi, ISeriesApi } from 'lightweight-charts';
import React, { useEffect, useRef } from 'react';

interface KlineChartProps {
  data: {
    time: string | number; // timestamp or date string
    open: number;
    high: number;
    low: number;
    close: number;
    ma20?: number;
    ma50?: number;
    bb_upper?: number;
    bb_lower?: number;
  }[];
  colors?: {
    backgroundColor?: string;
    lineColor?: string;
    textColor?: string;
    areaTopColor?: string;
    areaBottomColor?: string;
  };
}

export const KlineChart: React.FC<KlineChartProps> = (props) => {
  const {
    data,
    colors: {
      backgroundColor = 'white',
      lineColor = '#2962FF',
      textColor = 'black',
      areaTopColor = '#2962FF',
      areaBottomColor = 'rgba(41, 98, 255, 0.28)',
    } = {},
  } = props;

  const chartContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Use container dimensions
    const width = chartContainerRef.current.clientWidth;
    const height = chartContainerRef.current.clientHeight;

    const handleResize = () => {
        if (chartContainerRef.current) {
            chart.applyOptions({ 
                width: chartContainerRef.current.clientWidth,
                height: chartContainerRef.current.clientHeight
            });
        }
    };

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: backgroundColor },
        textColor,
      },
      width: width,
      height: height || 400, // Fallback if 0
      grid: {
        vertLines: { color: 'rgba(42, 46, 57, 0.5)' },
        horzLines: { color: 'rgba(42, 46, 57, 0.5)' },
      },
      timeScale: {
          timeVisible: true,
          secondsVisible: false,
          borderColor: '#1e293b', // darker border
          visible: true,
          rightOffset: 12,
          barSpacing: 10,
          fixLeftEdge: true,
          tickMarkFormatter: (time: number, tickMarkType: any, locale: any) => {
              const date = new Date(time * 1000);
              // Format: 14:30
              return date.toLocaleTimeString('zh-CN', { 
                  hour: '2-digit', 
                  minute: '2-digit', 
                  hour12: false
                  // timeZone: 'Asia/Shanghai' // Use system timezone
              });
          },
      },
      localization: {
          // Tooltip format
          timeFormatter: (time: number) => {
              const date = new Date(time * 1000);
              return date.toLocaleString('zh-CN', {
                  month: '2-digit',
                  day: '2-digit',
                  hour: '2-digit',
                  minute: '2-digit',
                  hour12: false
                  // timeZone: 'Asia/Shanghai' // Use system timezone
              });
          }
      },
      rightPriceScale: {
          borderColor: '#485c7b',
      },
    });
    
    const newSeries = chart.addCandlestickSeries({
        upColor: '#26a69a', 
        downColor: '#ef5350', 
        borderVisible: false, 
        wickUpColor: '#26a69a', 
        wickDownColor: '#ef5350', 
    });
    
    // MA Lines
    const ma20Series = chart.addLineSeries({ 
        color: '#fbbf24', // Yellow for MA20/BB Middle
        lineWidth: 1, 
        priceLineVisible: false, 
        crosshairMarkerVisible: false,
        title: 'MA20'
    });
    
    const ma50Series = chart.addLineSeries({ 
        color: '#8b5cf6', // Purple for MA50
        lineWidth: 2, 
        priceLineVisible: false, 
        crosshairMarkerVisible: false,
        title: 'MA50'
    });

    // Bollinger Bands (Upper/Lower)
    const bbUpperSeries = chart.addLineSeries({ 
        color: 'rgba(41, 98, 255, 0.5)', // Blue transparent
        lineWidth: 1, 
        priceLineVisible: false, 
        crosshairMarkerVisible: false,
        lineStyle: 2, // Dashed
        title: 'BB Up'
    });
    
    const bbLowerSeries = chart.addLineSeries({ 
        color: 'rgba(41, 98, 255, 0.5)', 
        lineWidth: 1, 
        priceLineVisible: false, 
        crosshairMarkerVisible: false,
        lineStyle: 2, // Dashed
        title: 'BB Low'
    });

    // Process and sort data
    const processedData = [...data]
      .map(d => {
        let time = d.time;
        if (typeof time === 'string') {
            time = new Date(time).getTime() / 1000;
        } else if (typeof time === 'number' && time > 2000000000) {
            time = time / 1000;
        }
        return { ...d, time: time as any };
      })
      .sort((a, b) => (a.time as number) - (b.time as number));

    // Deduplicate data by time (keep the last one if duplicates exist)
    const uniqueDataMap = new Map();
    processedData.forEach(item => {
        uniqueDataMap.set(item.time, item);
    });
    const uniqueData = Array.from(uniqueDataMap.values()).sort((a, b) => (a.time as number) - (b.time as number));

    newSeries.setData(uniqueData);
    
    const ma20Data = uniqueData.filter(d => d.ma20).map(d => ({ time: d.time, value: d.ma20! }));
    const ma50Data = uniqueData.filter(d => d.ma50).map(d => ({ time: d.time, value: d.ma50! }));
    const bbUpperData = uniqueData.filter(d => d.bb_upper).map(d => ({ time: d.time, value: d.bb_upper! }));
    const bbLowerData = uniqueData.filter(d => d.bb_lower).map(d => ({ time: d.time, value: d.bb_lower! }));
    
    ma20Series.setData(ma20Data);
    ma50Series.setData(ma50Data);
    bbUpperSeries.setData(bbUpperData);
    bbLowerSeries.setData(bbLowerData);

    chart.timeScale().fitContent();

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, [data, backgroundColor, lineColor, textColor, areaTopColor, areaBottomColor]);

  return (
    <div
      ref={chartContainerRef}
      style={{ width: '100%', height: '100%' }}
    />
  );
};
