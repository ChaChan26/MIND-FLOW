/*
Windows Core Audio COM peak metering for active video meeting / media playback detection.

Author: ChaChan26 <minhharry2006@gmail.com>
Copyright (c) 2026 ChaChan26. All rights reserved.
*/

using System;
using System.Runtime.InteropServices;

namespace MindFlow.Win32.Audio
{
    public class ComAudioMeter : IDisposable
    {
        [ComImport]
        [Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
        private class MMDeviceEnumerator
        {
        }

        private enum EDataFlow { eRender, eCapture, eAll }
        private enum ERole { eConsole, eMultimedia, eCommunications }

        [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IMMDeviceEnumerator
        {
            int NotImpl1();
            [PreserveSig]
            int GetDefaultAudioEndpoint(EDataFlow dataFlow, ERole role, out IMMDevice ppEndpoint);
        }

        [Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IMMDevice
        {
            [PreserveSig]
            int Activate(ref Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
        }

        [Guid("C02216F6-8C67-4B5B-9D00-D008E73E0064"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
        private interface IAudioMeterInformation
        {
            [PreserveSig]
            int GetPeakValue(out float pfPeak);
        }

        private IAudioMeterInformation? _meter;
        private readonly object _lock = new();

        public ComAudioMeter()
        {
            InitializeMeter();
        }

        private void InitializeMeter()
        {
            try
            {
                var enumerator = (IMMDeviceEnumerator)new MMDeviceEnumerator();
                int hr = enumerator.GetDefaultAudioEndpoint(EDataFlow.eRender, ERole.eMultimedia, out var device);
                if (hr == 0 && device != null)
                {
                    var iid = typeof(IAudioMeterInformation).GUID;
                    hr = device.Activate(ref iid, 1 /* CLSCTX_INPROC_SERVER */, IntPtr.Zero, out var audioObj);
                    if (hr == 0 && audioObj is IAudioMeterInformation meter)
                    {
                        _meter = meter;
                    }
                }
            }
            catch
            {
                // Graceful fallback on headless or audio-disabled systems
            }
        }

        public float GetPeakValue()
        {
            lock (_lock)
            {
                if (_meter == null)
                    InitializeMeter();

                if (_meter != null)
                {
                    try
                    {
                        int hr = _meter.GetPeakValue(out float peak);
                        if (hr == 0) return peak;
                    }
                    catch
                    {
                        _meter = null;
                    }
                }

                return 0.0f;
            }
        }

        public bool IsAudioPlaying(float threshold = 0.01f) => GetPeakValue() > threshold;

        public void Dispose()
        {
            lock (_lock)
            {
                _meter = null;
            }
        }
    }
}
