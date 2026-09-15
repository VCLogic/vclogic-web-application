import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Investor, InvestorComparison as Comparison } from "../../api/types";
import { InvestorComparison } from "./InvestorComparison";

afterEach(cleanup);

const investors: Investor[] = [
  {vc_slug:"yin",display_name:"Elizabeth Yin-like Investor",firm:"Hustle Fund",role:"Partner",disclosure:"",start_available:true,recurring_positive_rationales:[],recurring_negative_rationales:[]},
  {vc_slug:"phil",display_name:"Phil Nadel-like Investor",firm:"Forefront",role:"Partner",disclosure:"",start_available:true,recurring_positive_rationales:[],recurring_negative_rationales:[]},
];

it("preserves comparison order and presents founder-safe metrics", () => {
  const comparison: Comparison = {
    comparison_id:"c1",project_id:"p1",version_id:"v1",selected_vc_slugs:["yin","phil"],status:"complete",created_at:"",updated_at:"",missing_vc_slugs:[],
    assessments:[
      {assessment_id:"a1",vc_slug:"yin",status:"complete",decision:"In",investment_likelihood:.61,decision_confidence:.68,positive_rationales:[],negative_rationales:[],unresolved_rationales:[],relative_fit:{percentile:89,reference_count:53},highest_estimated_fit:true,leading_group:true},
      {assessment_id:"a2",vc_slug:"phil",status:"complete",decision:"Out",investment_likelihood:.42,decision_confidence:.72,positive_rationales:[],negative_rationales:[],unresolved_rationales:[],relative_fit:{percentile:74,reference_count:21},highest_estimated_fit:false,leading_group:false},
    ],
  };
  render(<InvestorComparison comparison={comparison} investors={investors} onView={vi.fn()} onRehearse={vi.fn()}/>);

  expect(screen.getByText("Highest historical fit")).toBeVisible();
  expect(screen.getAllByText("Estimated investor fit")[0]).toBeVisible();
  expect(screen.getAllByText("Historical fit percentile")[0]).toBeVisible();
  expect(screen.getAllByText("Assessment confidence")[0]).toBeVisible();
  expect(screen.getByText("61/100")).toBeVisible();
  expect(screen.getByText("89th percentile")).toBeVisible();
  const names=screen.getAllByRole("heading",{level:3}).map(node=>node.textContent);
  expect(names).toEqual(["Elizabeth Yin-like Investor","Phil Nadel-like Investor"]);
});
