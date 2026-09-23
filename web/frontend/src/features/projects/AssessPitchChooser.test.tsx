import { QueryClient,QueryClientProvider } from "@tanstack/react-query";
import { cleanup,render,screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter,Route,Routes } from "react-router-dom";
import { afterEach,expect,it,vi } from "vitest";
import { api } from "../../api/client";
import { AssessPitchChooser } from "./AssessPitchChooser";

afterEach(()=>{cleanup();vi.restoreAllMocks()});
const project={project_id:"p1",display_name:"ShiftPilot",company_aliases:["ShiftPilot"],created_at:"2026-09-01T00:00:00Z",updated_at:"2026-09-01T00:00:00Z",current_version_id:"v1",version_count:1,assessment_count:1,rehearsal_count:0,versions:[{version_id:"v1",project_id:"p1",created_at:"2026-09-01T00:00:00Z",pitch_sha256:"a".repeat(64),character_count:100}]};
function setup(){vi.spyOn(api,"profile").mockResolvedValue({investor:{vc_slug:"yin",investor_version_id:"b".repeat(64),display_name:"Elizabeth Yin-like Investor",firm:"Hustle Fund",role:"Partner",disclosure:"Simulation",start_available:true,recurring_positive_rationales:[],recurring_negative_rationales:[]},sections:[]});vi.spyOn(api,"projects").mockResolvedValue({projects:[project]});vi.spyOn(api,"project").mockResolvedValue(project);}
function renderPage(){render(<QueryClientProvider client={new QueryClient()}><MemoryRouter initialEntries={["/assess/yin"]}><Routes><Route path="/assess/:vcSlug" element={<AssessPitchChooser/>}/><Route path="/pitches/:projectId/versions/:versionId" element={<p>Pitch workspace</p>}/></Routes></MemoryRouter></QueryClientProvider>)}

it("assesses an existing immutable pitch version",async()=>{setup();const user=userEvent.setup();const start=vi.spyOn(api,"startAssessment").mockResolvedValue({assessment_id:"a1",status:"complete",event_url:"/events"});renderPage();await user.selectOptions(await screen.findByLabelText("Pitch project"),"p1");await user.click(screen.getByRole("checkbox",{name:/authorize provider api costs/i}));await user.click(screen.getByRole("button",{name:"Assess selected pitch"}));expect(start).toHaveBeenCalledWith("p1","v1","yin","b".repeat(64));expect(await screen.findByText("Pitch workspace")).toBeVisible()});

it("saves a new pitch without calling a provider",async()=>{setup();const user=userEvent.setup();const create=vi.spyOn(api,"createProject").mockResolvedValue(project);const start=vi.spyOn(api,"startAssessment");renderPage();await user.click(await screen.findByRole("tab",{name:/create a new pitch/i}));await user.type(screen.getByLabelText(/company name/i),"ShiftPilot");await user.type(screen.getByLabelText(/^pitch text/i),"Founder pitch");await user.click(screen.getByRole("button",{name:"Save pitch only"}));expect(create).toHaveBeenCalled();expect(start).not.toHaveBeenCalled();expect(await screen.findByText("Pitch workspace")).toBeVisible()});
