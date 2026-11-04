"use client";

import { MainLayout } from "@/components/layout";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Tabs, TabPanel } from "@/components/ui/Tabs";
import { Select } from "@/components/ui/Dropdown";
import { Upload, Download, Save, Zap, Shield, AlertCircle, CheckCircle, Settings, Database, Image, Bell, Moon, Sun, Key, Globe, Lock, Users, ChevronDown } from "lucide-react";
import { formatRelativeTime } from "@/lib/utils";

export default function SettingsPage() {
  return (
    <MainLayout title="Settings" subtitle="Configure your Amazon Image Automation preferences">
      <div className="space-y-6">
        <Tabs tabs={[
          { key: "general", label: "General", icon: <Settings className="w-4 h-4" /> },
          { key: "gemini", label: "Gemini", icon: <Zap className="w-4 h-4" /> },
          { key: "watermark", label: "Watermark", icon: <Shield className="w-4 h-4" /> },
          { key: "scraper", label: "Scraper", icon: <Database className="w-4 h-4" /> },
          { key: "output", label: "Output", icon: <Image className="w-4 h-4" /> },
          { key: "notifications", label: "Notifications", icon: <Bell className="w-4 h-4" /> },
          { key: "account", label: "Account", icon: <Users className="w-4 h-4" /> },
        ]} onChange={() => {}} className="mb-6">
          <TabPanel active={true}>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Application</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div>
                    <label className="label">Application Name</label>
                    <Input placeholder="Amazon Image Automation" defaultValue="Amazon Image Automation" />
                  </div>
                  <div>
                    <label className="label">Default Output Directory</label>
                    <Input placeholder="./output" defaultValue="./output" />
                    <p className="input-hint">Where generated images and manifests are stored</p>
                  </div>
                  <div>
                    <label className="label">Default ASIN Domain</label>
                    <Select
                      placeholder="Select domain"
                      options={[
                        { value: "amazon.in", label: "Amazon India (amazon.in)" },
                        { value: "amazon.com", label: "Amazon US (amazon.com)" },
                        { value: "amazon.co.uk", label: "Amazon UK (amazon.co.uk)" },
                        { value: "amazon.de", label: "Amazon Germany (amazon.de)" },
                        { value: "amazon.ae", label: "Amazon UAE (amazon.ae)" },
                      ]}
                      defaultValue="amazon.in"
                    />
                    <p className="input-hint">Default marketplace for ASIN lookups</p>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Auto-save prompts</p>
                      <p className="text-body-sm text-surface-500">Automatically save generated prompts to disk</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" defaultChecked />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Debug mode</p>
                      <p className="text-body-sm text-surface-500">Enable verbose logging for debugging</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Chrome Profile</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div>
                    <label className="label">Chrome Profile Name</label>
                    <Input placeholder="Chirag" defaultValue="Chirag" />
                    <p className="input-hint">The Chrome profile name shown in Chrome's profile picker</p>
                  </div>
                  <div>
                    <label className="label">Chrome Channel</label>
                    <Select
                      placeholder="Select channel"
                      options={[
                        { value: "chrome", label: "Google Chrome (stable)" },
                        { value: "chromium", label: "Chromium" },
                      ]}
                      defaultValue="chrome"
                    />
                  </div>
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Use own Chrome profile</p>
                      <p className="text-body-sm text-surface-500">Use your signed-in Chrome session (recommended)</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" defaultChecked />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Recopy Chrome profile</p>
                      <p className="text-body-sm text-surface-500">Refresh the profile copy from Chrome on startup</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabPanel>

          <TabPanel active={false}>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Gemini Web Configuration</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Enable Gemini</p>
                      <p className="text-body-sm text-surface-500">Enable image generation via Gemini web UI</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" defaultChecked />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                  <div>
                    <label className="label">Gemini URL</label>
                    <Input placeholder="https://gemini.google.com/app" defaultValue="https://gemini.google.com/app" />
                  </div>
                  <div>
                    <label className="label">Images Page URL</label>
                    <Input placeholder="https://gemini.google.com/images" defaultValue="https://gemini.google.com/images" />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Max Reference Images</label>
                      <Input type="number" defaultValue="6" />
                    </div>
                    <div>
                      <label className="label">Aspect Ratio</label>
                      <Input placeholder="3:4" defaultValue="3:4" />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Generation Timeout (sec)</label>
                      <Input type="number" defaultValue="180" />
                    </div>
                    <div>
                      <label className="label">Upload Wait (sec)</label>
                      <Input type="number" defaultValue="8" />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Slot Retries</label>
                      <Input type="number" defaultValue="2" />
                    </div>
                    <div>
                      <label className="label">Retry Delay (sec)</label>
                      <div className="flex gap-2">
                        <Input type="number" placeholder="10" style={{ width: '60px' }} />
                        <span className="self-center text-surface-500">to</span>
                        <Input type="number" placeholder="20" style={{ width: '60px' }} />
                      </div>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <h4 className="font-medium text-surface-900">Image Model Hints (priority order)</h4>
                    <div className="space-y-2">
                      {["Create image", "Nano Banana", "Imagen", "Image generation", "Image"].map((hint, i) => (
                        <div key={i} className="flex items-center gap-2 p-2 bg-surface-50 rounded-lg">
                          <span className="w-6 text-surface-400">{i + 1}.</span>
                          <Input defaultValue={hint} />
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">New chat per slot</p>
                      <p className="text-body-sm text-surface-500">Start fresh chat for each image (slower but isolated)</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Send master prompt</p>
                      <p className="text-body-sm text-surface-500">Send AIIE master message as first chat message</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Ensure image model</p>
                      <p className="text-body-sm text-surface-500">Force selection of image-capable model before generation</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" defaultChecked />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Ensure image model every slot</p>
                      <p className="text-body-sm text-surface-500">Re-select Create image before EVERY image (strict)</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" defaultChecked />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Attach references every slot</p>
                      <p className="text-body-sm text-surface-500">Re-upload base images before each panel generation</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" defaultChecked />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Model Picker Selectors</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-body-sm text-surface-500">CSS selectors for finding the model picker button (first match wins)</p>
                  <div className="space-y-2">
                    {[
                      'button[aria-label*="model" i]',
                      '[data-test-id*="model-selector" i]',
                      'button:has-text("Fast")',
                      'button:has-text("Pro")',
                    ].map((selector, i) => (
                      <div key={i} className="flex items-center gap-2 p-2 bg-surface-50 rounded-lg">
                        <span className="w-6 text-surface-400">{i + 1}.</span>
                        <Input defaultValue={selector} />
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabPanel>

          <TabPanel active={false}>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Watermark Engine</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Enable Watermark Removal</p>
                      <p className="text-body-sm text-surface-500">Automatically remove Veo/Gemini sparkles from generated images</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" defaultChecked />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Engine Directory</label>
                      <Input placeholder="G:\\veo-watermark-remover\\veo-watermark-remover\\local_app" defaultValue="G:\\veo-watermark-remover\\veo-watermark-remover\\local_app" />
                    </div>
                    <div>
                      <label className="label">Python Executable</label>
                      <Input placeholder="auto-detect" defaultValue="" placeholder="Auto-detect from engine venv" />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Model Path</label>
                      <Input placeholder="models/lama_fp32.onnx" defaultValue="models/lama_fp32.onnx" />
                    </div>
                    <div>
                      <label className="label">Device</label>
                      <Select
                        placeholder="Select device"
                        options={[
                          { value: "auto", label: "Auto (CUDA if available)" },
                          { value: "cpu", label: "CPU only" },
                          { value: "cuda", label: "CUDA GPU" },
                        ]}
                        defaultValue="cpu"
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Threads (0 = auto)</label>
                      <Input type="number" defaultValue="0" />
                    </div>
                    <div>
                      <label className="label">Timeout per Image (sec)</label>
                      <Input type="number" defaultValue="180" />
                    </div>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Fail-safe mode</p>
                      <p className="text-body-sm text-surface-500">Never break the run on watermark errors</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" defaultChecked />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Detection Settings</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Primary Gate (IoU)</label>
                      <Input type="number" step="0.01" defaultValue="0.70" />
                    </div>
                    <div>
                      <label className="label">Near-match Gate</label>
                      <Input placeholder="0.55 - 0.70" defaultValue="0.55" />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Family Gate</label>
                      <Input type="number" step="0.01" defaultValue="0.60" />
                    </div>
                    <div>
                      <label className="label">Ghost Threshold (grey levels)</label>
                      <Input type="number" step="0.1" defaultValue="3.0" />
                    </div>
                  </div>
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Re-fill on re-detection</p>
                      <p className="text-body-sm text-surface-500">Re-run inpainting with wider mask if mark re-detects</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" defaultChecked />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                  <div>
                    <label className="label">Re-fill Mask Pad</label>
                    <Input type="number" defaultValue="14" />
                    <p className="input-hint">Padding for wider re-fill mask (pixels)</p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabPanel>

          <TabPanel active={false}>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Amazon Scraper</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Amazon Domain</label>
                      <Select
                        placeholder="Select domain"
                        options={[
                          { value: "amazon.in", label: "Amazon India (amazon.in)" },
                          { value: "amazon.com", label: "Amazon US (amazon.com)" },
                          { value: "amazon.co.uk", label: "Amazon UK (amazon.co.uk)" },
                          { value: "amazon.de", label: "Amazon Germany (amazon.de)" },
                          { value: "amazon.ae", label: "Amazon UAE (amazon.ae)" },
                        ]}
                        defaultValue="amazon.in"
                      />
                    </div>
                    <div>
                      <label className="label">Locale</label>
                      <Input placeholder="en-IN" defaultValue="en-IN" />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Max Gallery Images</label>
                      <Input type="number" defaultValue="12" />
                    </div>
                    <div>
                      <label className="label">Min Image Size (px)</label>
                      <Input type="number" defaultValue="500" />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Scroll Passes</label>
                      <Input type="number" defaultValue="4" />
                    </div>
                    <div>
                      <label className="label">Page Timeout (ms)</label>
                      <Input type="number" defaultValue="45000" />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">Delay Between ASINs (sec)</label>
                      <div className="flex gap-2">
                        <Input type="number" placeholder="4" style={{ width: '60px' }} />
                        <span className="self-center text-surface-500">to</span>
                        <Input type="number" placeholder="9" style={{ width: '60px' }} />
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Captcha Handling</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <p className="text-body-sm text-surface-500">Text patterns that indicate a captcha page</p>
                  <div className="space-y-2">
                    {[
                      "Enter the characters you see below",
                      "Type the characters you see in this image",
                      "/errors/validateCaptcha",
                      "api-services-support@amazon.com",
                    ].map((pattern, i) => (
                      <div key={i} className="flex items-center gap-2 p-2 bg-surface-50 rounded-lg">
                        <span className="w-6 text-surface-400">{i + 1}.</span>
                        <Input defaultValue={pattern} />
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabPanel>

          <TabPanel active={false}>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Output Directory</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div>
                    <label className="label">Output Root Directory</label>
                    <Input placeholder="./output" defaultValue="./output" />
                  </div>
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Keep Base Images</p>
                      <p className="text-body-sm text-surface-500">Retain downloaded base images after generation</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" defaultChecked />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                  <div>
                    <label className="label">Image Spec - Size (px)</label>
                    <Input type="number" defaultValue="3000" />
                  </div>
                  <div>
                    <label className="label">Image Spec - Aspect Ratio</label>
                    <Input placeholder="1:1" defaultValue="1:1" />
                  </div>
                  <div>
                    <label className="label">Color Space</label>
                    <Input placeholder="sRGB" defaultValue="sRGB" />
                  </div>
                  <div>
                    <label className="label">Minimum File Size (bytes)</label>
                    <Input type="number" defaultValue="60000" />
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Tracking Sheet</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Enable Tracking</p>
                      <p className="text-body-sm text-surface-500">Log ASIN job status to CSV or Google Sheets</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" defaultChecked />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                  <div>
                    <label className="label">Backend</label>
                    <Select
                      placeholder="Select backend"
                      options={[
                        { value: "csv", label: "CSV file" },
                        { value: "gspread", label: "Google Sheets" },
                      ]}
                      defaultValue="csv"
                    />
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="label">CSV Path</label>
                      <Input placeholder="data/tracking.csv" defaultValue="data/tracking.csv" />
                    </div>
                    <div>
                      <label className="label">Spreadsheet ID</label>
                      <Input placeholder="from Google Sheet URL" defaultValue="" />
                    </div>
                  </div>
                  <div>
                    <label className="label">Worksheet Name</label>
                    <Input placeholder="ASIN Jobs" defaultValue="ASIN Jobs" />
                  </div>
                  <div>
                    <label className="label">Credentials File</label>
                    <Input placeholder="service-account.json" defaultValue="service-account.json" />
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabPanel>

          <TabPanel active={false}>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Email Notifications</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Enable Email Notifications</p>
                      <p className="text-body-sm text-surface-500">Send email alerts for job events</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                  <div>
                    <label className="label">Recipients (one per line)</label>
                    <textarea className="textarea" rows={4} placeholder="user1@example.com&#10;user2@example.com" />
                  </div>
                  <div className="space-y-4">
                    <h4 className="font-medium text-surface-900">Notify on</h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {[
                        { label: "Job completed", default: true },
                        { label: "Job failed", default: true },
                        { label: "Watermark ghost detected", default: true },
                        { label: "Scraping completed", default: false },
                        { label: "Daily summary", default: false },
                      ].map((item, i) => (
                        <label key={i} className="flex items-center gap-3 p-3 bg-surface-50 rounded-lg cursor-pointer">
                          <input type="checkbox" className="w-4 h-4 text-brand-500 rounded" defaultChecked={item.default} />
                          <span className="text-body-sm text-surface-700">{item.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Slack Notifications</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                    <div>
                      <p className="font-medium text-surface-900">Enable Slack Notifications</p>
                      <p className="text-body-sm text-surface-500">Send Slack messages for job events</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" />
                      <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                    </label>
                  </div>
                  <div>
                    <label className="label">Slack Webhook URL</label>
                    <Input placeholder="https://hooks.slack.com/services/..." />
                    <p className="input-hint">Create an Incoming Webhook in your Slack app settings</p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabPanel>

          <TabPanel active={false}>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Profile</CardTitle>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-full bg-brand-500 flex items-center justify-center text-white text-2xl font-bold">
                      CJ
                    </div>
                    <div>
                      <p className="heading-md font-semibold">Chirag Patel</p>
                      <p className="text-body-sm text-surface-500">easysell.gemini@gmail.com</p>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div>
                      <label className="label">Display Name</label>
                      <Input defaultValue="Chirag Patel" />
                    </div>
                    <div>
                      <label className="label">Email</label>
                      <Input type="email" defaultValue="easysell.gemini@gmail.com" disabled />
                      <p className="input-hint">Email cannot be changed</p>
                    </div>
                    <div className="flex items-center justify-between p-4 bg-surface-50 rounded-lg">
                      <div>
                        <p className="font-medium text-surface-900">Two-factor authentication</p>
                        <p className="text-body-sm text-surface-500">Add an extra layer of security</p>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" className="sr-only peer" defaultChecked />
                        <div className="w-11 h-6 bg-surface-300 peer-focus:ring-2 peer-focus:ring-brand-500 rounded-full peer peer-checked:bg-brand-500 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border after:rounded-full after:h-5 after:w-5 after:transition-all"></div>
                      </label>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Change Password</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Input type="password" placeholder="Current password" />
                  <Input type="password" placeholder="New password" />
                  <Input type="password" placeholder="Confirm new password" />
                  <Button variant="primary">Update Password</Button>
                </CardContent>
              </Card>
            </div>
          </TabPanel>
        </Tabs>
      </div>
    </MainLayout>
  );
}